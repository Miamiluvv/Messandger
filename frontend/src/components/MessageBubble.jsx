import { useState, useRef, useEffect } from 'react'
import { Reply, Pencil, Trash2, MoreHorizontal, Smile, Play, Pause, FileText, Download, Mic, Check, CheckCheck, Clock } from 'lucide-react'
import api from '../api/axios'
import Avatar from './Avatar'
import PollMessage from './PollMessage'

const QUICK_EMOJIS = ['👍', '❤️', '😂', '😮', '😢', '🔥', '👏', '🎉']

export default function MessageBubble({ msg, isMine, onReply, onEdit, onDelete, chatId }) {
  const [showMenu, setShowMenu] = useState(false)
  const [showEmojiPicker, setShowEmojiPicker] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [voiceProgress, setVoiceProgress] = useState(0)
  const [voiceDuration, setVoiceDuration] = useState(0)
  const [voiceCurrentTime, setVoiceCurrentTime] = useState(0)
  const audioRef = useRef(null)
  const [localReactions, setLocalReactions] = useState(msg.reactions || [])

  if (msg.is_deleted) {
    return (
      <div className={`flex ${isMine ? 'justify-end' : 'justify-start'} mb-1`}>
        <div className="px-3 py-2 rounded-2xl bg-dark-800/50 italic text-dark-500 text-xs">Сообщение удалено</div>
      </div>
    )
  }

  const time = new Date(msg.created_at).toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' })

  const handleReaction = async (emoji) => {
    try {
      const res = await api.post(`/chats/${chatId}/messages/${msg.id}/reactions`, { emoji })
      if (res.data.action === 'added') {
        setLocalReactions((prev) => [...prev, { emoji, user_id: 'me', id: res.data.id }])
      } else {
        setLocalReactions((prev) => {
          const idx = prev.findIndex((r) => r.emoji === emoji && (r.user_id === 'me' || true))
          if (idx >= 0) return [...prev.slice(0, idx), ...prev.slice(idx + 1)]
          return prev
        })
      }
    } catch (e) {}
    setShowEmojiPicker(false)
  }

  const isVoice = msg.message_type === 'voice'
  const isFile = msg.message_type === 'file'
  const isImage = msg.message_type === 'image'
  const isVideo = msg.message_type === 'video'
  const isPoll = msg.message_type === 'poll'

  return (
    <div className={`flex ${isMine ? 'justify-end' : 'justify-start'} group mb-1`} onMouseLeave={() => { setShowMenu(false); setShowEmojiPicker(false) }}>
      <div className={`max-w-[70%] relative ${isMine ? 'order-2' : ''}`}>
        {/* Sender name for groups */}
        {!isMine && msg.sender_name && (
          <p className="text-xs text-primary-400 font-medium mb-0.5 ml-1">{msg.sender_name}</p>
        )}

        {/* Reply preview */}
        {msg.reply_to && (
          <div className={`ml-1 mb-1 pl-2 border-l-2 border-primary-500 ${isMine ? 'border-primary-300' : ''}`}>
            <p className="text-[10px] text-primary-400 font-medium">{msg.reply_to.sender_name}</p>
            <p className="text-[10px] text-dark-400 truncate">{msg.reply_to.content}</p>
          </div>
        )}

        <div className={`${isMine ? 'chat-bubble-sent' : 'chat-bubble-received'} relative`}>
          {/* Attachments (skipped for voice — rendered by custom waveform below) */}
          {!isVoice && msg.attachments?.length > 0 && (
            <div className="mb-1 space-y-1">
              {msg.attachments.map((a) => (
                <div key={a.id}>
                  {a.file_type?.startsWith('image') ? (
                    <img src={a.file_url} alt={a.file_name} className="rounded-lg max-h-64 object-cover cursor-pointer hover:opacity-90" onClick={() => window.open(a.file_url, '_blank')} />
                  ) : a.file_type?.startsWith('video') ? (
                    <video src={a.file_url} controls className="rounded-lg max-h-48 w-full" />
                  ) : a.file_type?.startsWith('audio') ? (
                    <audio src={a.file_url} controls className="w-full max-w-xs" />
                  ) : (
                    <a href={a.file_url} target="_blank" download className="flex items-center gap-2 bg-dark-700/50 rounded-lg p-2.5 hover:bg-dark-700 transition-colors">
                      <div className="w-8 h-8 bg-primary-600/20 rounded-lg flex items-center justify-center flex-shrink-0">
                        <FileText size={14} className="text-primary-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs text-white truncate">{a.file_name}</p>
                        <p className="text-[10px] text-dark-400">{formatFileSize(a.file_size)}</p>
                      </div>
                      <Download size={14} className="text-dark-400" />
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Voice message */}
          {isVoice && msg.attachments?.[0] && (
            <div className="flex items-center gap-3 min-w-[220px] max-w-[280px]">
              <button onClick={() => {
                const audio = audioRef.current
                if (!audio) return
                if (playing) { audio.pause() } else { audio.play() }
                setPlaying(!playing)
              }} className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 transition-all ${playing ? 'bg-red-500 hover:bg-red-600 shadow-lg shadow-red-500/20' : isMine ? 'bg-white/20 hover:bg-white/30' : 'bg-primary-600 hover:bg-primary-700 shadow-lg shadow-primary-500/20'}`} title={playing ? 'Пауза' : 'Воспроизвести'}>
                {playing ? <Pause size={16} className="text-white" /> : <Play size={16} className="text-white ml-0.5" />}
              </button>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1 mb-1.5">
                  {/* Waveform bars */}
                  {Array.from({ length: 20 }).map((_, i) => {
                    const h = Math.sin(i * 0.8 + (msg.id?.charCodeAt?.(0) || 0)) * 0.5 + 0.5
                    const filled = voiceDuration > 0 ? (i / 20) <= voiceProgress : false
                    return <div key={i} className={`w-[3px] rounded-full transition-all duration-100 ${filled ? (isMine ? 'bg-white' : 'bg-primary-400') : (isMine ? 'bg-white/25' : 'bg-dark-500')}`} style={{ height: `${8 + h * 14}px` }} />
                  })}
                </div>
                <div className="flex items-center justify-between">
                  <span className={`text-[10px] font-mono ${isMine ? 'text-primary-100' : 'text-dark-400'}`}>
                    {playing ? formatVoiceTime(voiceCurrentTime) : formatVoiceTime(voiceDuration)}
                  </span>
                  <Mic size={10} className={isMine ? 'text-primary-200' : 'text-dark-500'} />
                </div>
              </div>
              <audio
                ref={audioRef}
                src={msg.attachments[0].file_url}
                onLoadedMetadata={(e) => setVoiceDuration(e.target.duration || 0)}
                onTimeUpdate={(e) => {
                  setVoiceCurrentTime(e.target.currentTime)
                  setVoiceProgress(e.target.duration ? e.target.currentTime / e.target.duration : 0)
                }}
                onEnded={() => { setPlaying(false); setVoiceProgress(0); setVoiceCurrentTime(0) }}
                className="hidden"
              />
            </div>
          )}

          {/* Poll */}
          {isPoll && msg.poll && <PollMessage poll={msg.poll} isMine={isMine} />}

          {/* Text content */}
          {msg.content && !isVoice && !isPoll && (
            <p className="text-sm whitespace-pre-wrap break-words">{renderContent(msg.content)}</p>
          )}

          <div className="flex items-center justify-end gap-1 mt-0.5">
            {msg.is_edited && <span className="text-[10px] text-dark-400 italic">ред.</span>}
            <span className={`text-[10px] ${isMine ? 'text-primary-200' : 'text-dark-400'}`}>{time}</span>
            {isMine && <MessageStatus msg={msg} />}
          </div>
        </div>

        {/* Reactions */}
        {localReactions.length > 0 && (
          <div className="flex gap-0.5 mt-0.5 flex-wrap">
            {groupReactions(localReactions).map(([emoji, count]) => (
              <button key={emoji} onClick={() => handleReaction(emoji)} className="bg-dark-800 border border-dark-600 rounded-full px-1.5 py-0.5 text-xs hover:bg-dark-700 transition-colors cursor-pointer">
                {emoji} {count > 1 && count}
              </button>
            ))}
          </div>
        )}

        {/* Context menu trigger */}
        <div className="absolute -top-2 right-0 opacity-0 group-hover:opacity-100 flex gap-0.5 transition-opacity">
          <button onClick={() => setShowEmojiPicker(!showEmojiPicker)} className="p-1 bg-dark-800 rounded-full border border-dark-600" title="Реакция">
            <Smile size={12} className="text-dark-400" />
          </button>
          <button onClick={() => setShowMenu(!showMenu)} className="p-1 bg-dark-800 rounded-full border border-dark-600" title="Действия">
            <MoreHorizontal size={12} className="text-dark-400" />
          </button>
        </div>

        {/* Emoji quick picker */}
        {showEmojiPicker && (
          <div className={`absolute top-6 ${isMine ? 'right-0' : 'left-0'} z-50 bg-dark-800 border border-dark-600 rounded-xl shadow-xl p-2 flex gap-1`}>
            {QUICK_EMOJIS.map((e) => (
              <button key={e} onClick={() => handleReaction(e)} className="w-7 h-7 rounded hover:bg-dark-700 flex items-center justify-center text-sm">
                {e}
              </button>
            ))}
          </div>
        )}

        {/* Context menu */}
        {showMenu && (
          <div className={`absolute top-6 ${isMine ? 'right-8' : 'left-8'} z-50 bg-dark-800 border border-dark-600 rounded-xl shadow-xl py-1 min-w-[140px]`}>
            <button onClick={() => { onReply(msg); setShowMenu(false) }} className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-dark-300 hover:bg-dark-700 hover:text-white">
              <Reply size={12} /> Ответить
            </button>
            {isMine && msg.message_type === 'text' && (
              <button onClick={() => { onEdit(msg); setShowMenu(false) }} className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-dark-300 hover:bg-dark-700 hover:text-white">
                <Pencil size={12} /> Редактировать
              </button>
            )}
            {isMine && (
              <button onClick={() => { onDelete(msg); setShowMenu(false) }} className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-red-400 hover:bg-dark-700">
                <Trash2 size={12} /> Удалить
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function MessageStatus({ msg }) {
  // States: sending (optimistic), sent (default), read (is_read === true)
  if (msg.sending) return <Clock size={11} className="text-primary-200/70" />
  if (msg.is_read) return <CheckCheck size={13} className="text-blue-300" />
  return <Check size={13} className="text-primary-200/90" />
}

function groupReactions(reactions) {
  const map = {}
  reactions.forEach((r) => { map[r.emoji] = (map[r.emoji] || 0) + 1 })
  return Object.entries(map)
}

function formatVoiceTime(seconds) {
  if (!seconds || isNaN(seconds)) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function formatFileSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return bytes + ' Б'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' КБ'
  return (bytes / 1048576).toFixed(1) + ' МБ'
}

function renderContent(text) {
  if (!text) return null
  const urlRegex = /(https?:\/\/[^\s]+)/g
  const parts = text.split(urlRegex)
  return parts.map((part, i) =>
    urlRegex.test(part) ? <a key={i} href={part} target="_blank" rel="noopener" className="text-primary-400 hover:underline break-all">{part}</a> : part
  )
}
