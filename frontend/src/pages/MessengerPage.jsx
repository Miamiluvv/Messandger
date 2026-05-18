import { useEffect, useState } from 'react'
import { useAuthStore } from '../store/authStore'
import { useChatStore } from '../store/chatStore'
import { useWebSocketStore } from '../store/websocketStore'
import Sidebar from '../components/Sidebar'
import ChatWindow from '../components/ChatWindow'
import EmptyState from '../components/EmptyState'
import CallsTab from '../components/CallsTab'

export default function MessengerPage() {
  const { fetchUser, token } = useAuthStore()
  const { fetchChats, activeChat } = useChatStore()
  const { connect } = useWebSocketStore()
  const [activeTab, setActiveTab] = useState('chats') // chats | calls

  useEffect(() => {
    fetchUser()
    fetchChats()
    if (token) connect(token)
  }, [])

  return (
    <div className="h-screen flex bg-dark-950">
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />
      <div className="flex-1 flex">
        {activeTab === 'chats' && (activeChat ? <ChatWindow /> : <EmptyState />)}
        {activeTab === 'calls' && <CallsTab />}
      </div>
    </div>
  )
}
