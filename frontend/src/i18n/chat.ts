/**
 * 聊天界面多语言翻译
 */

type ChatTextKey =
  | 'input_placeholder'
  | 'send'
  | 'loading'
  | 'search_placeholder'
  | 'search'
  | 'no_results'
  | 'today'
  | 'yesterday'
  | 'confirm'
  | 'cancel'
  | 'system_command'
  | 'system_response'
  | 'welcome'
  | 'lang_auto'
  | 'lang_zh'
  | 'lang_en'

const translations: Record<string, Record<ChatTextKey, string>> = {
  zh: {
    input_placeholder: '输入消息...',
    send: '发送',
    loading: '思考中...',
    search_placeholder: '搜索聊天记录...',
    search: '搜索',
    no_results: '没有找到相关消息',
    today: '今天',
    yesterday: '昨天',
    confirm: '确认',
    cancel: '取消',
    system_command: '系统指令',
    system_response: '系统响应',
    welcome: '你好！我是 AI 助手，有什么可以帮你的？',
    lang_auto: '自动',
    lang_zh: '中文',
    lang_en: 'EN',
  },
  en: {
    input_placeholder: 'Type a message...',
    send: 'Send',
    loading: 'Thinking...',
    search_placeholder: 'Search chat history...',
    search: 'Search',
    no_results: 'No messages found',
    today: 'Today',
    yesterday: 'Yesterday',
    confirm: 'Confirm',
    cancel: 'Cancel',
    system_command: 'System Command',
    system_response: 'System Response',
    welcome: 'Hello! I\'m the AI assistant. How can I help you?',
    lang_auto: 'Auto',
    lang_zh: '中文',
    lang_en: 'EN',
  },
}

export function getChatText(key: ChatTextKey, lang?: string | null): string {
  const effectiveLang = lang || 'zh'
  return translations[effectiveLang]?.[key] || translations.zh[key]
}
