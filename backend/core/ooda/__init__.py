"""OODA loop phases: Observe -> Orient -> Decide -> Act"""
from core.ooda.intent import IntentResult, IntentRecognitionService, IntentRecognitionStrategy
from core.ooda.observe import ObservePhase, Observation, observe_phase
from core.ooda.orient import OrientPhase, Orientation, get_orient_phase
from core.ooda.decide import DecidePhase, OodaDecision, get_decide_phase
from core.ooda.act import ActPhase, OodaActionResult, get_act_phase
from core.ooda.loop import OodaLoop, OodaLoopResult, get_ooda_loop

__all__ = [
    "IntentResult", "IntentRecognitionService", "IntentRecognitionStrategy",
    "ObservePhase", "Observation", "observe_phase",
    "OrientPhase", "Orientation", "get_orient_phase",
    "DecidePhase", "OodaDecision", "get_decide_phase",
    "ActPhase", "OodaActionResult", "get_act_phase",
    "OodaLoop", "OodaLoopResult", "get_ooda_loop",
]
