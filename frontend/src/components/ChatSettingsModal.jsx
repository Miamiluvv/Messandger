import { useState } from 'react'
import { X, Settings, Trash2 } from 'lucide-react'
import api from '../api/axios'
import toast from 'react-hot-toast'
import { useChatStore } from '../store/chatStore'
import Avatar from './Avatar'
import { confirmDelete } from '../store/confirmStore'

export default function ChatSettingsModal({ chat, onClose }) {
  const [name, setName] = useState(chat.name || '')
  const [description, setDescription] = useState(chat.description || '')
  const [showDeletedLabel, setShowDeletedLabel] = useState(chat.show_deleted_label !== false)
  const { fetchChats } = useChatStore()

  const handleSave = async () => {
    try {
      await api.put(`/chats/${chat.id}/settings`, {
        name: name.trim(),
        description: description.trim(),
        show_deleted_label: showDeletedLabel,
      })
      toast.success('Настройки сохранены')
      fetchChats()
      onClose()
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Ошибка')
    }
  }

  const handleRemoveMember = async (userId, memberName) => {
    if (!(await confirmDelete(`Удалить «${memberName}» из чата?`))) return
    try {
      await api.delete(`/chats/${chat.id}/members/${userId}`)
      toast.success('Участник удалён')
      fetchChats()
    } catch (e) {
      toast.error('Ошибка')
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-dark-900 rounded-2xl border border-dark-700 shadow-2xl w-full max-w-md max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-dark-700">
          <h3 className="text-lg font-bold text-white flex items-center gap-2"><Settings size={20} className="text-primary-400" /> Настройки чата</h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-dark-700 text-dark-400 hover:text-white"><X size={20} /></button>
        </div>

        <div className="p-4 space-y-4 overflow-y-auto">
          <div>
            <label className="block text-xs font-medium text-dark-300 mb-1">Название</label>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} className="input-field" />
          </div>
          <div>
            <label className="block text-xs font-medium text-dark-300 mb-1">Описание</label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} className="input-field" rows={2} />
          </div>

          {chat.chat_type === 'group' && (
            <div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={showDeletedLabel} onChange={(e) => setShowDeletedLabel(e.target.checked)} className="w-4 h-4 rounded accent-primary-600" />
                <span className="text-sm text-dark-300">Показывать «Сообщение удалено»</span>
              </label>
              <p className="text-xs text-dark-500 mt-1">Если выключено — удалённые сообщения исчезают бесследно</p>
            </div>
          )}

          {/* Members list */}
          <div>
            <label className="block text-xs font-medium text-dark-300 mb-2">Участники ({chat.members?.length})</label>
            <div className="space-y-1 max-h-48 overflow-y-auto">
              {chat.members?.map((m) => (
                <div key={m.user_id} className="flex items-center justify-between px-2 py-1.5 rounded-lg hover:bg-dark-800">
                  <div className="flex items-center gap-2">
                    <Avatar name={m.first_name} url={m.avatar_url} size="sm" />
                    <div>
                      <p className="text-xs text-white">{m.first_name} {m.last_name}</p>
                      <p className="text-[10px] text-dark-400">{m.role === 'owner' ? 'Владелец' : m.role === 'admin' ? 'Админ' : m.role === 'readonly' ? 'Только чтение' : 'Участник'}</p>
                    </div>
                  </div>
                  {m.role !== 'owner' && (
                    <button onClick={() => handleRemoveMember(m.user_id, `${m.first_name} ${m.last_name}`)} className="p-1 text-dark-400 hover:text-red-400"><Trash2 size={14} /></button>
                  )}
                </div>
              ))}
            </div>
          </div>

          <button onClick={handleSave} className="btn-primary w-full">Сохранить</button>
        </div>
      </div>
    </div>
  )
}
