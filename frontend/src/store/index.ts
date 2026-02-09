import { create } from 'zustand'
import type { Employee, ChatMessage, DashboardStats, Room, StayRecord, Task, ConversationMessage } from '../types'
export { useOntologyStore } from './ontologyStore'

// 认证状态
interface AuthState {
  user: Employee | null
  token: string | null
  isAuthenticated: boolean
  login: (user: Employee, token: string) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: JSON.parse(localStorage.getItem('user') || 'null'),
  token: localStorage.getItem('token'),
  isAuthenticated: !!localStorage.getItem('token'),
  login: (user, token) => {
    localStorage.setItem('user', JSON.stringify(user))
    localStorage.setItem('token', token)
    set({ user, token, isAuthenticated: true })
  },
  logout: () => {
    localStorage.removeItem('user')
    localStorage.removeItem('token')
    set({ user: null, token: null, isAuthenticated: false })
  }
}))

// 聊天状态
interface ChatState {
  messages: ChatMessage[]
  isLoading: boolean
  hasMore: boolean
  oldestTimestamp: string | null
  currentTopicId: string | null
  searchResults: ConversationMessage[]
  isSearching: boolean
  searchKeyword: string
  historyLoaded: boolean
  language: string | null  // null = auto-detect, "zh", "en"
  addMessage: (message: ChatMessage) => void
  prependMessages: (messages: ChatMessage[]) => void
  setMessages: (messages: ChatMessage[]) => void
  setLoading: (loading: boolean) => void
  setHasMore: (hasMore: boolean) => void
  setOldestTimestamp: (timestamp: string | null) => void
  setCurrentTopicId: (topicId: string | null) => void
  setSearchResults: (results: ConversationMessage[]) => void
  setIsSearching: (isSearching: boolean) => void
  setSearchKeyword: (keyword: string) => void
  setHistoryLoaded: (loaded: boolean) => void
  setLanguage: (lang: string | null) => void
  clearMessages: () => void
  clearSearch: () => void
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isLoading: false,
  hasMore: false,
  oldestTimestamp: null,
  currentTopicId: null,
  searchResults: [],
  isSearching: false,
  searchKeyword: '',
  historyLoaded: false,
  language: localStorage.getItem('chat_language') as string | null,
  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message]
  })),
  prependMessages: (messages) => set((state) => ({
    messages: [...messages, ...state.messages]
  })),
  setMessages: (messages) => set({ messages }),
  setLoading: (loading) => set({ isLoading: loading }),
  setHasMore: (hasMore) => set({ hasMore }),
  setOldestTimestamp: (timestamp) => set({ oldestTimestamp: timestamp }),
  setCurrentTopicId: (topicId) => set({ currentTopicId: topicId }),
  setSearchResults: (results) => set({ searchResults: results }),
  setIsSearching: (isSearching) => set({ isSearching }),
  setSearchKeyword: (keyword) => set({ searchKeyword: keyword }),
  setHistoryLoaded: (loaded) => set({ historyLoaded: loaded }),
  setLanguage: (lang) => {
    if (lang) {
      localStorage.setItem('chat_language', lang)
    } else {
      localStorage.removeItem('chat_language')
    }
    set({ language: lang })
  },
  clearMessages: () => set({
    messages: [],
    hasMore: false,
    oldestTimestamp: null,
    currentTopicId: null,
    historyLoaded: false
  }),
  clearSearch: () => set({ searchResults: [], searchKeyword: '', isSearching: false })
}))

// 仪表盘数据状态
interface DashboardState {
  stats: DashboardStats | null
  rooms: Room[]
  activeStays: StayRecord[]
  pendingTasks: Task[]
  isLoading: boolean
  setStats: (stats: DashboardStats) => void
  setRooms: (rooms: Room[]) => void
  setActiveStays: (stays: StayRecord[]) => void
  setPendingTasks: (tasks: Task[]) => void
  setLoading: (loading: boolean) => void
}

export const useDashboardStore = create<DashboardState>((set) => ({
  stats: null,
  rooms: [],
  activeStays: [],
  pendingTasks: [],
  isLoading: false,
  setStats: (stats) => set({ stats }),
  setRooms: (rooms) => set({ rooms }),
  setActiveStays: (stays) => set({ activeStays: stays }),
  setPendingTasks: (tasks) => set({ pendingTasks: tasks }),
  setLoading: (loading) => set({ isLoading: loading })
}))

// UI 状态
interface UIState {
  sidebarCollapsed: boolean
  activeModal: string | null
  modalData: unknown
  toggleSidebar: () => void
  openModal: (name: string, data?: unknown) => void
  closeModal: () => void
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  activeModal: null,
  modalData: null,
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  openModal: (name, data) => set({ activeModal: name, modalData: data }),
  closeModal: () => set({ activeModal: null, modalData: null })
}))
