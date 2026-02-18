"""
core/ai/reflexion.py

ReflexionLoop - Self-healing action execution with LLM-based reflection.

Based on: "Reflexion: Language Agents with Verbal Reinforcement Learning"
https://arxiv.org/abs/2303.11366

The ReflexionLoop enables automatic recovery from execution errors by:
1. Capturing execution errors
2. Using LLM to analyze what went wrong
3. Generating corrected parameters
4. Retrying with corrections
5. Falling back to rule-based engine after max retries
"""
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from pydantic import ValidationError

if TYPE_CHECKING:
    from core.ai.llm_client import LLMClient
    from core.ai.actions import ActionRegistry

logger = logging.getLogger(__name__)


# ==================== Error Types ====================

class ErrorType:
    """Standard error type classifications for reflection."""

    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"
    VALUE_ERROR = "value_error"
    STATE_ERROR = "state_error"
    UNKNOWN = "unknown"


class ExecutionError(Exception):
    """
    Standardized execution error for reflection.

    Wraps any exception into a structured format that can be
    analyzed by the LLM for error correction.

    Attributes:
        error_type: Category of error (from ErrorType)
        message: Human-readable error message
        suggestions: List of suggestions for fixing the error
        context: Additional contextual information
        original_error: The original exception (optional)
    """

    def __init__(
        self,
        error_type: str,
        message: str,
        suggestions: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        self.error_type = error_type
        self.message = message
        self.suggestions = suggestions or []
        self.context = context or {}
        self.original_error = original_error
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "error_type": self.error_type,
            "message": self.message,
            "suggestions": self.suggestions,
            "context": self.context
        }

    def __repr__(self) -> str:
        return f"ExecutionError(error_type={self.error_type}, message={self.message})"

    def to_prompt_string(self) -> str:
        """Format as string for LLM prompt."""
        lines = [
            f"**Type:** {self.error_type}",
            f"**Message:** {self.message}"
        ]
        if self.suggestions:
            lines.append(f"**Suggestions:**")
            for suggestion in self.suggestions:
                lines.append(f"  - {suggestion}")
        if self.context:
            lines.append(f"**Context:** {json.dumps(self.context, ensure_ascii=False)}")
        return "\n".join(lines)

    @classmethod
    def from_exception(cls, error: Exception, context: Optional[Dict[str, Any]] = None) -> "ExecutionError":
        """
        Create ExecutionError from an exception.

        Classifies the error type based on exception type and message.

        Args:
            error: The exception to wrap
            context: Additional context information

        Returns:
            ExecutionError instance
        """
        error_type = ErrorType.UNKNOWN
        message = str(error)
        suggestions = []

        # Classify by exception type
        if isinstance(error, ValidationError):
            error_type = ErrorType.VALIDATION_ERROR
            # Extract validation errors for better suggestions
            try:
                error_dict = json.loads(error.json()) if hasattr(error, 'json') else {}
                if isinstance(error_dict, list):
                    for e in error_dict:
                        loc = e.get('loc', [])
                        msg = e.get('msg', '')
                        if loc and msg:
                            param = ".".join(str(x) for x in loc)
                            suggestions.append(f"Parameter '{param}': {msg}")
            except Exception:
                suggestions.append("Check that all required parameters are provided")
                suggestions.append("Verify parameter types match the schema")

        elif isinstance(error, PermissionError):
            error_type = ErrorType.PERMISSION_DENIED
            suggestions.append("This operation requires elevated permissions")
            suggestions.append("Contact your administrator if you believe you should have access")

        elif isinstance(error, (ValueError, TypeError)):
            error_type = ErrorType.VALUE_ERROR
            message_lower = message.lower()

            # Date-related errors
            if "date" in message_lower or "time" in message_lower:
                suggestions.append("Use ISO date format (YYYY-MM-DD)")

            # Number-related errors
            elif "invalid literal" in message_lower or "could not convert" in message_lower:
                suggestions.append("Ensure numeric values are valid numbers")

            # Invalid enum/choice
            elif "not a valid" in message_lower or "invalid choice" in message_lower:
                suggestions.append("Check that enum values match allowed options")

        # Check for "not found" pattern before other checks
        if "not found" in message.lower() or "does not exist" in message.lower():
            error_type = ErrorType.NOT_FOUND
            suggestions.append("Verify the ID exists in the system")
            suggestions.append("Check for typos in entity names or IDs")

        # State-related errors
        if "state" in message.lower() or "status" in message.lower():
            if error_type == ErrorType.UNKNOWN:
                error_type = ErrorType.STATE_ERROR
            suggestions.append("Check the current state of the entity")
            suggestions.append("Ensure the state transition is valid")

        return cls(
            error_type=error_type,
            message=message,
            suggestions=suggestions,
            context=context or {},
            original_error=error
        )


@dataclass
class ReflectionResult:
    """
    Result of LLM reflection on an execution error.

    Contains the LLM's analysis and suggested corrections.

    Attributes:
        analysis: LLM's explanation of what went wrong
        correction: LLM's suggested correction strategy
        corrected_params: Parameters after correction (null if not applicable)
        confidence: LLM's confidence score (0.0 to 1.0)
        should_retry: Whether retry is worth attempting
    """

    analysis: str
    correction: str
    corrected_params: Optional[Dict[str, Any]] = None
    confidence: float = 0.5
    should_retry: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "analysis": self.analysis,
            "correction": self.correction,
            "corrected_params": self.corrected_params,
            "confidence": self.confidence,
            "should_retry": self.should_retry
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReflectionResult":
        """Create from dictionary (parsed from LLM response)."""
        return cls(
            analysis=data.get("analysis", ""),
            correction=data.get("correction", ""),
            corrected_params=data.get("corrected_params"),
            confidence=float(data.get("confidence", 0.5)),
            should_retry=bool(data.get("should_retry", True))
        )


@dataclass
class AttemptRecord:
    """Record of a single execution attempt."""

    attempt_number: int
    params: Dict[str, Any]
    success: bool
    error: Optional[ExecutionError] = None
    result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "attempt_number": self.attempt_number,
            "params": self.params,
            "success": self.success,
            "error": self.error.to_dict() if self.error else None,
            "result": self.result
        }


# ==================== Reflexion Loop ====================

class ReflexionLoop:
    """
    Self-healing action execution loop with LLM-based reflection.

    Implements the Reflexion pattern: when an action fails, use LLM
    to analyze the error and generate corrections, then retry.

    Features:
    - Automatic retry up to MAX_RETRIES times
    - LLM-based error analysis and parameter correction
    - Attempt history tracking for debugging
    - Fallback to rule-based engine (optional)
    - Skip reflection for non-reflectable errors (e.g., permission)

    Example:
        ```python
        loop = ReflexionLoop(llm_client, action_registry)
        result = loop.execute_with_reflexion(
            "walkin_checkin",
            {"guest_name": "张三", "room_id": 999},
            {"db": db_session, "user": current_user}
        )
        ```
    """

    MAX_RETRIES = 2
    MIN_CONFIDENCE_FOR_RETRY = 0.3

    def __init__(
        self,
        llm_client: Optional["LLMClient"],
        action_registry: "ActionRegistry",
        rule_engine: Optional[Any] = None,
        max_retries: int = MAX_RETRIES
    ):
        """
        Initialize ReflexionLoop.

        Args:
            llm_client: LLM client for reflection (can be None)
            action_registry: ActionRegistry for dispatching actions
            rule_engine: Optional rule engine for fallback
            max_retries: Maximum retry attempts (default: MAX_RETRIES)
        """
        self.llm_client = llm_client
        self.action_registry = action_registry
        self.rule_engine = rule_engine
        self.max_retries = max_retries
        self._attempt_records: List[AttemptRecord] = []

    def get_attempt_history(self) -> List[Dict[str, Any]]:
        """
        Return all attempt records from the most recent execution.

        Returns:
            List of attempt record dictionaries with attempt_number, params,
            success, error, and result fields.
        """
        return [r.to_dict() for r in self._attempt_records]

    def execute_with_reflexion(
        self,
        action_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute action with self-healing retry loop.

        Flow:
        1. Try execution with current params
        2. On error, normalize to ExecutionError
        3. Check if error is reflectable
        4. Generate reflection using LLM
        5. Update params from reflection
        6. Retry (up to max_retries times)
        7. Fall back to rule engine if available
        8. Raise ExecutionError if all attempts fail

        Args:
            action_name: Name of action to execute
            params: Initial parameters
            context: Execution context (db, user, etc.)

        Returns:
            Dict containing:
                - result: Execution result
                - attempts: List of attempt records
                - reflexion_used: Whether reflection was used

        Raises:
            ExecutionError: If all attempts fail
        """
        original_params = params.copy()
        current_params = params.copy()
        error_history: List[ExecutionError] = []
        attempt_records: List[AttemptRecord] = []
        self._attempt_records = attempt_records
        reflexion_used = False

        for attempt in range(self.max_retries + 1):
            attempt_number = attempt
            logger.info(f"ReflexionLoop: Attempt {attempt_number} for action '{action_name}'")

            try:
                # Execute action
                result = self.action_registry.dispatch(
                    action_name,
                    current_params,
                    context
                )

                # Success - record and return
                attempt_records.append(AttemptRecord(
                    attempt_number=attempt_number,
                    params=current_params.copy(),
                    success=True,
                    result=result
                ))

                logger.info(f"ReflexionLoop: Success on attempt {attempt_number}")

                return {
                    "result": result,
                    "attempts": [r.to_dict() for r in attempt_records],
                    "reflexion_used": reflexion_used,
                    "final_attempt": attempt_number
                }

            except Exception as e:
                # Normalize error
                exec_error = ExecutionError.from_exception(e, context={
                    "action_name": action_name,
                    "attempt": attempt_number
                })
                error_history.append(exec_error)

                attempt_records.append(AttemptRecord(
                    attempt_number=attempt_number,
                    params=current_params.copy(),
                    success=False,
                    error=exec_error
                ))

                logger.warning(f"ReflexionLoop: Attempt {attempt_number} failed: {exec_error.message}")

                # Check if we should retry
                if attempt >= self.max_retries:
                    logger.info(f"ReflexionLoop: Max retries ({self.max_retries}) exceeded")
                    break

                # Check if error is reflectable
                if not self._should_attempt_reflexion(exec_error):
                    logger.info(f"ReflexionLoop: Error type '{exec_error.error_type}' not reflectable, stopping")
                    break

                # Try auto-correction first (cheaper than LLM)
                auto_corrected = self._auto_correct_params(
                    action_name, current_params, exec_error
                )
                if auto_corrected is not None:
                    current_params = auto_corrected
                    logger.info("ReflexionLoop: Auto-corrected params, retrying")
                    reflexion_used = True
                    continue

                # For state errors, try querying current state
                if exec_error.error_type == ErrorType.STATE_ERROR:
                    state_correction = self._handle_state_error(
                        action_name, current_params, exec_error, context
                    )
                    if state_correction is not None:
                        current_params = state_correction
                        logger.info("ReflexionLoop: State error handled, retrying with corrected params")
                        reflexion_used = True
                        continue

                # Check if LLM is available
                if not self.llm_client or not self.llm_client.is_enabled():
                    logger.warning("ReflexionLoop: LLM not available, cannot reflect")
                    break

                # Generate reflection
                try:
                    reflection = self._generate_reflection(
                        action_name=action_name,
                        original_params=original_params,
                        current_params=current_params,
                        error=exec_error,
                        error_history=error_history
                    )

                    reflexion_used = True

                    logger.info(f"ReflexionLoop: Reflection generated (confidence={reflection.confidence:.2f})")
                    logger.debug(f"ReflexionLoop: Analysis: {reflection.analysis}")

                    # Check if reflection suggests retrying
                    if not reflection.should_retry:
                        logger.info("ReflexionLoop: Reflection suggests not retrying")
                        break

                    # Check confidence threshold
                    if reflection.confidence < self.MIN_CONFIDENCE_FOR_RETRY:
                        logger.info(f"ReflexionLoop: Confidence {reflection.confidence:.2f} below threshold {self.MIN_CONFIDENCE_FOR_RETRY}")
                        break

                    # Update params if correction provided
                    if reflection.corrected_params is not None:
                        current_params = reflection.corrected_params
                        logger.info(f"ReflexionLoop: Updated params from reflection")
                    else:
                        logger.warning("ReflexionLoop: No corrected params provided, retrying with same params")

                except Exception as reflection_error:
                    logger.error(f"ReflexionLoop: Reflection generation failed: {reflection_error}")
                    # Continue to next attempt with original params
                    break

        # All attempts failed - try fallback
        if self.rule_engine:
            logger.info("ReflexionLoop: Trying fallback to rule engine")
            try:
                fallback_result = self._try_fallback(
                    action_name,
                    original_params,
                    context,
                    error_history
                )

                attempt_records.append(AttemptRecord(
                    attempt_number=self.max_retries + 1,
                    params=original_params,
                    success=True,
                    result=fallback_result
                ))

                return {
                    "result": fallback_result,
                    "attempts": [r.to_dict() for r in attempt_records],
                    "reflexion_used": reflexion_used,
                    "final_attempt": self.max_retries + 1,
                    "fallback_used": True
                }

            except Exception as fallback_error:
                logger.error(f"ReflexionLoop: Fallback also failed: {fallback_error}")

        # All attempts failed - raise ExecutionError with context
        # Use the last error's type and message if available
        last_error = error_history[-1] if error_history else None
        final_error = ExecutionError(
            error_type=last_error.error_type if last_error else ErrorType.UNKNOWN,
            message=f"Action '{action_name}' failed after {len(attempt_records)} attempts",
            suggestions=last_error.suggestions if last_error else [
                "Check the error history for details",
                "Verify all parameters are correct",
                "Ensure the required resources exist"
            ],
            context={
                "action_name": action_name,
                "attempts": len(attempt_records),
                "error_history": [e.to_dict() for e in error_history],
                "last_error": last_error.to_dict() if last_error else None
            },
            original_error=last_error.original_error if last_error else None
        )

        raise final_error

    def _should_attempt_reflexion(self, error: ExecutionError) -> bool:
        """
        Determine if error is worth reflecting on.

        Non-reflectable errors:
        - permission_denied: Reflection won't help (user lacks permission)
        - Some state errors: May require external action

        Args:
            error: The execution error

        Returns:
            True if reflection should be attempted
        """
        # Permission errors are never reflectable
        if error.error_type == ErrorType.PERMISSION_DENIED:
            return False

        # All other errors are potentially reflectable
        return True

    def _generate_reflection(
        self,
        action_name: str,
        original_params: Dict[str, Any],
        current_params: Dict[str, Any],
        error: ExecutionError,
        error_history: List[ExecutionError]
    ) -> ReflectionResult:
        """
        Use LLM to analyze error and generate correction.

        Constructs a reflection prompt with:
        - Action definition and schema
        - Original and current parameters
        - Error information
        - Error history

        Parses LLM response into ReflectionResult.

        Args:
            action_name: Name of the action
            original_params: Parameters from first attempt
            current_params: Parameters that caused current error
            error: Current execution error
            error_history: All previous errors

        Returns:
            ReflectionResult with analysis and corrections

        Raises:
            Exception: If LLM call fails or response is unparsable
        """
        # Get action definition
        action_def = self.action_registry.get_action(action_name)
        if not action_def:
            raise ValueError(f"Unknown action: {action_name}")

        # Build prompt
        prompt = self._build_reflection_prompt(
            action_def=action_def,
            original_params=original_params,
            current_params=current_params,
            error=error,
            error_history=error_history
        )

        # Call LLM
        response = self.llm_client.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,  # Lower temperature for more deterministic analysis
            max_tokens=1000,
            response_format={"type": "json_object"}
        )

        # Parse response
        result_dict = response.to_json()
        if not result_dict:
            # Fallback to empty reflection if LLM didn't return valid JSON
            return ReflectionResult(
                analysis="Unable to parse LLM response",
                correction="No correction available",
                should_retry=False,
                confidence=0.0
            )

        return ReflectionResult.from_dict(result_dict)

    def _build_reflection_prompt(
        self,
        action_def: Any,
        original_params: Dict[str, Any],
        current_params: Dict[str, Any],
        error: ExecutionError,
        error_history: List[ExecutionError]
    ) -> str:
        """Build the reflection prompt for the LLM."""
        # Get parameter schema
        schema = action_def.parameters_schema.model_json_schema()

        lines = [
            "You executed an action, but it failed. Please analyze the error and suggest corrections.",
            "",
            "**Action Definition:**",
            f"Name: {action_def.name}",
            f"Entity: {action_def.entity}",
            f"Description: {action_def.description}",
            "",
            "**Parameter Schema:**",
            "```json",
            json.dumps(schema, ensure_ascii=False, indent=2),
            "```",
            "",
            "**Original Parameters:**",
            "```json",
            json.dumps(original_params, ensure_ascii=False, indent=2),
            "```",
            "",
            "**Current Parameters (that failed):**",
            "```json",
            json.dumps(current_params, ensure_ascii=False, indent=2),
            "```",
            "",
            "**Error Information:**",
            error.to_prompt_string(),
        ]

        # Add error history if available (excluding the current error)
        if error_history and len(error_history) > 1:
            lines.append("")
            lines.append("**Error History:**")
            for i, hist_error in enumerate(error_history[:-1], 1):  # Exclude current error
                lines.append(f"{i}. {hist_error.error_type}: {hist_error.message}")

        lines.append("")
        lines.append("**Your Task:**")
        lines.append("1. Analyze what went wrong")
        lines.append("2. Determine if parameters can be corrected")
        lines.append("3. If yes, provide corrected parameters")
        lines.append("4. If no, explain why not")
        lines.append("")
        lines.append("**Response Format (JSON):**")
        lines.append("```json")
        lines.append("{")
        lines.append('    "analysis": "Explanation of the root cause",')
        lines.append('    "correction": "Strategy for fixing the issue",')
        lines.append('    "corrected_params": {...} or null,')
        lines.append('    "confidence": 0.8,')
        lines.append('    "should_retry": true')
        lines.append("}")
        lines.append("```")

        return "\n".join(lines)

    def _auto_correct_params(
        self,
        action_name: str,
        params: Dict[str, Any],
        error: ExecutionError
    ) -> Optional[Dict[str, Any]]:
        """
        Attempt rule-based (non-LLM) parameter correction.

        Tries cheap, deterministic corrections before resorting to LLM reflection:
        - Date format: "2026-2-8" -> "2026-02-08"
        - Enum normalization: "active" -> "ACTIVE", "vacant clean" -> "vacant_clean"
        - Number string conversion: "301" -> 301 for integer fields

        Args:
            action_name: Name of the action
            params: Current parameters
            error: The execution error

        Returns:
            Corrected parameters dict if corrections were made, None otherwise
        """
        action_def = self.action_registry.get_action(action_name)
        if action_def is None:
            return None

        schema = action_def.parameters_schema.model_json_schema()
        properties = schema.get("properties", {})
        defs = schema.get("$defs", {})
        corrected = params.copy()
        any_corrected = False

        for field_name, field_info in properties.items():
            if field_name not in corrected:
                continue

            value = corrected[field_name]
            field_type = field_info.get("type", "string")

            # Resolve $ref to get the actual field definition
            resolved_info = field_info
            if "$ref" in field_info:
                ref_path = field_info["$ref"]  # e.g., "#/$defs/RoomStatus"
                ref_name = ref_path.rsplit("/", 1)[-1]
                if ref_name in defs:
                    resolved_info = defs[ref_name]
                    field_type = resolved_info.get("type", field_type)

            # Handle allOf with $ref (Pydantic sometimes uses allOf for required refs)
            if "allOf" in field_info:
                for item in field_info["allOf"]:
                    if "$ref" in item:
                        ref_path = item["$ref"]
                        ref_name = ref_path.rsplit("/", 1)[-1]
                        if ref_name in defs:
                            resolved_info = defs[ref_name]
                            field_type = resolved_info.get("type", field_type)
                            break

            # Handle anyOf patterns (Optional fields)
            if "anyOf" in field_info:
                for opt in field_info["anyOf"]:
                    if opt.get("type") == "null":
                        continue
                    if "$ref" in opt:
                        ref_path = opt["$ref"]
                        ref_name = ref_path.rsplit("/", 1)[-1]
                        if ref_name in defs:
                            resolved_info = defs[ref_name]
                            field_type = resolved_info.get("type", field_type)
                    else:
                        field_type = opt.get("type", "string")
                    break

            # Date format correction: "2026-2-8" -> "2026-02-08"
            if isinstance(value, str) and (
                "date" in field_name.lower()
                or resolved_info.get("format") == "date"
                or field_info.get("format") == "date"
            ):
                date_match = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', value)
                if date_match:
                    year, month, day = date_match.groups()
                    normalized = f"{year}-{int(month):02d}-{int(day):02d}"
                    if normalized != value:
                        corrected[field_name] = normalized
                        any_corrected = True
                        logger.info(
                            f"ReflexionLoop: Auto-corrected date '{value}' -> '{normalized}' "
                            f"for field '{field_name}'"
                        )

            # Enum value normalization (check resolved_info for $ref'd enums)
            enum_values = resolved_info.get("enum") or field_info.get("enum")
            if enum_values and isinstance(value, str):
                # Try exact match first (already correct)
                if value not in enum_values:
                    # Try case-insensitive match
                    matched = None
                    for ev in enum_values:
                        if isinstance(ev, str) and ev.lower() == value.lower():
                            matched = ev
                            break
                    # Try underscore/space normalization
                    if matched is None:
                        normalized_value = value.replace(" ", "_")
                        for ev in enum_values:
                            if isinstance(ev, str) and ev.lower() == normalized_value.lower():
                                matched = ev
                                break
                    if matched is not None:
                        corrected[field_name] = matched
                        any_corrected = True
                        logger.info(
                            f"ReflexionLoop: Auto-corrected enum '{value}' -> '{matched}' "
                            f"for field '{field_name}'"
                        )

            # Number string conversion: "301" -> 301 for integer fields
            if field_type == "integer" and isinstance(value, str):
                try:
                    corrected[field_name] = int(value)
                    any_corrected = True
                    logger.info(
                        f"ReflexionLoop: Auto-corrected number string '{value}' -> {int(value)} "
                        f"for field '{field_name}'"
                    )
                except (ValueError, TypeError):
                    pass

            # Number string to float conversion
            if field_type == "number" and isinstance(value, str):
                try:
                    corrected[field_name] = float(value)
                    any_corrected = True
                    logger.info(
                        f"ReflexionLoop: Auto-corrected number string '{value}' -> {float(value)} "
                        f"for field '{field_name}'"
                    )
                except (ValueError, TypeError):
                    pass

        return corrected if any_corrected else None

    def _handle_state_error(
        self,
        action_name: str,
        params: Dict[str, Any],
        error: ExecutionError,
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Handle state errors by querying entity current state via registry.

        For state errors, queries the action definition to understand valid
        state transitions and suggests corrections.

        Args:
            action_name: Name of the action
            params: Current parameters
            error: The state error
            context: Execution context

        Returns:
            Corrected parameters if state-based correction is possible, None otherwise
        """
        action_def = self.action_registry.get_action(action_name)
        if action_def is None:
            return None

        # Extract state information from error message
        error_msg = error.message.lower()

        # Look for valid state alternatives in error context or suggestions
        valid_alternatives = error.context.get("valid_alternatives", [])
        if not valid_alternatives and error.suggestions:
            # Try to extract state hints from suggestions
            for suggestion in error.suggestions:
                if "valid" in suggestion.lower() or "transition" in suggestion.lower():
                    valid_alternatives.append(suggestion)

        # If we have the entity's current state info in the error context,
        # include it for the caller / next retry
        corrected = params.copy()
        current_state = error.context.get("current_state")

        if current_state:
            corrected["_entity_current_state"] = current_state
            logger.info(
                f"ReflexionLoop: State error - entity current state is '{current_state}'"
            )
            return corrected

        if valid_alternatives:
            corrected["_valid_state_alternatives"] = valid_alternatives
            logger.info(
                f"ReflexionLoop: State error - valid alternatives: {valid_alternatives}"
            )
            return corrected

        return None

    def _try_fallback(
        self,
        action_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
        error_history: List[ExecutionError]
    ) -> Dict[str, Any]:
        """
        Try fallback execution using rule engine.

        Args:
            action_name: Name of action
            params: Parameters to use
            context: Execution context
            error_history: Error history for context

        Returns:
            Result from rule engine

        Raises:
            Exception: If rule engine fails or is not available
        """
        if not self.rule_engine:
            raise ValueError("No rule engine available for fallback")

        # Try to call fallback method on rule engine
        if hasattr(self.rule_engine, 'fallback'):
            return self.rule_engine.fallback(
                action_name=action_name,
                params=params,
                context=context,
                error_history=error_history
            )
        else:
            raise ValueError("Rule engine does not have fallback method")


__all__ = [
    "ErrorType",
    "ExecutionError",
    "ReflectionResult",
    "AttemptRecord",
    "ReflexionLoop",
]
