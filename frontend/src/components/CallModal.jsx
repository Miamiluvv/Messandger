import { useState, useEffect, useRef, useCallback } from 'react'
import { Phone, PhoneOff, Mic, MicOff, Video, VideoOff, Monitor, MonitorOff, UserPlus, X } from 'lucide-react'
import { useCallStore } from '../store/callStore'
import { useWebSocketStore } from '../store/websocketStore'
import { useAuthStore } from '../store/authStore'
import api from '../api/axios'
import toast from 'react-hot-toast'

const ICE_SERVERS = [
  { urls: 'stun:stun.l.google.com:19302' },
  { urls: 'stun:stun1.l.google.com:19302' },
  { urls: 'stun:stun2.l.google.com:19302' },
]

export default function CallModal() {
  const {
    activeCall, incomingCall, callStatus,
    isMuted, isCameraOff, isScreenSharing,
    localStream, remoteStreams, peerConnections,
    setActiveCall, setIncomingCall, setCallStatus,
    toggleMute, toggleCamera, setScreenSharing,
    setLocalStream, addRemoteStream, removeRemoteStream,
    addPeerConnection, cleanup
  } = useCallStore()

  const { ws } = useWebSocketStore()
  const { user } = useAuthStore()
  const localVideoRef = useRef(null)
  const remoteVideoRefs = useRef({})
  const [callDuration, setCallDuration] = useState(0)
  const durationInterval = useRef(null)

  // Start duration timer when active
  useEffect(() => {
    if (callStatus === 'active') {
      setCallDuration(0)
      durationInterval.current = setInterval(() => setCallDuration(d => d + 1), 1000)
    } else {
      if (durationInterval.current) clearInterval(durationInterval.current)
    }
    return () => { if (durationInterval.current) clearInterval(durationInterval.current) }
  }, [callStatus])

  // Assign local stream to video element
  useEffect(() => {
    if (localVideoRef.current && localStream) {
      localVideoRef.current.srcObject = localStream
    }
  }, [localStream])

  // Assign remote streams
  useEffect(() => {
    Object.entries(remoteStreams).forEach(([peerId, stream]) => {
      const el = remoteVideoRefs.current[peerId]
      if (el && el.srcObject !== stream) {
        el.srcObject = stream
      }
    })
  }, [remoteStreams])

  const createPeerConnection = useCallback((peerId) => {
    const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS })

    pc.onicecandidate = (event) => {
      if (event.candidate && ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: 'call_signal',
          call_id: activeCall?.id,
          signal_type: 'ice-candidate',
          signal: event.candidate,
          recipients: [peerId],
        }))
      }
    }

    pc.ontrack = (event) => {
      addRemoteStream(peerId, event.streams[0])
    }

    pc.onconnectionstatechange = () => {
      if (pc.connectionState === 'disconnected' || pc.connectionState === 'failed') {
        removeRemoteStream(peerId)
      }
    }

    // Add local tracks
    if (localStream) {
      localStream.getTracks().forEach(track => pc.addTrack(track, localStream))
    }

    addPeerConnection(peerId, pc)
    return pc
  }, [ws, activeCall, localStream, addRemoteStream, removeRemoteStream, addPeerConnection])

  // Handle incoming WebRTC signals
  const handleSignal = useCallback(async (data) => {
    const { signal_type, signal, from_user, call_id } = data

    if (call_id !== activeCall?.id) return

    let pc = peerConnections[from_user]
    if (!pc) {
      pc = createPeerConnection(from_user)
    }

    if (signal_type === 'offer') {
      await pc.setRemoteDescription(new RTCSessionDescription(signal))
      const answer = await pc.createAnswer()
      await pc.setLocalDescription(answer)
      ws?.send(JSON.stringify({
        type: 'call_signal',
        call_id,
        signal_type: 'answer',
        signal: answer,
        recipients: [from_user],
      }))
    } else if (signal_type === 'answer') {
      await pc.setRemoteDescription(new RTCSessionDescription(signal))
    } else if (signal_type === 'ice-candidate') {
      try {
        await pc.addIceCandidate(new RTCIceCandidate(signal))
      } catch (e) { /* ignore */ }
    }
  }, [activeCall, peerConnections, createPeerConnection, ws])

  // Start outgoing call
  const startCall = useCallback(async (callType, participantIds, callId) => {
    try {
      const constraints = { audio: true, video: callType === 'video' }
      const stream = await navigator.mediaDevices.getUserMedia(constraints)
      setLocalStream(stream)
      setCallStatus('ringing')
      setActiveCall({ id: callId, type: callType, participants: participantIds, isOutgoing: true })

      // Send invite via WS
      ws?.send(JSON.stringify({
        type: 'call_invite',
        call_id: callId,
        call_type: callType,
        from_name: `${user?.first_name} ${user?.last_name}`,
        from_avatar: user?.avatar_url,
        recipients: participantIds,
      }))

      // Timeout if no answer
      setTimeout(() => {
        const state = useCallStore.getState()
        if (state.callStatus === 'ringing') {
          endCall()
          toast.error('Нет ответа')
        }
      }, 30000)
    } catch (err) {
      toast.error('Нет доступа к микрофону/камере')
      cleanup()
    }
  }, [ws, user, setLocalStream, setCallStatus, setActiveCall, cleanup])

  // Accept incoming call
  const acceptCall = useCallback(async () => {
    if (!incomingCall) return
    try {
      const constraints = { audio: true, video: incomingCall.call_type === 'video' }
      const stream = await navigator.mediaDevices.getUserMedia(constraints)
      setLocalStream(stream)
      setActiveCall({
        id: incomingCall.call_id,
        type: incomingCall.call_type,
        participants: [incomingCall.from_user],
        isOutgoing: false
      })
      setCallStatus('connecting')
      setIncomingCall(null)

      // Notify caller we accepted; the caller will create the offer
      ws?.send(JSON.stringify({
        type: 'call_accept',
        call_id: incomingCall.call_id,
        recipients: [incomingCall.from_user],
      }))

      // Join call in backend
      try { await api.post(`/calls/${incomingCall.call_id}/join`) } catch (e) { /* ignore */ }

      // Pre-create peer connection so handleSignal finds it on offer arrival
      createPeerConnection(incomingCall.from_user)
      setCallStatus('active')
    } catch (err) {
      toast.error('Нет доступа к микрофону/камере')
      rejectCall()
    }
  }, [incomingCall, ws, setLocalStream, setActiveCall, setCallStatus, setIncomingCall, createPeerConnection])

  // Reject incoming call
  const rejectCall = useCallback(() => {
    if (!incomingCall) return
    ws?.send(JSON.stringify({
      type: 'call_reject',
      call_id: incomingCall.call_id,
      recipients: [incomingCall.from_user],
    }))
    setIncomingCall(null)
  }, [incomingCall, ws, setIncomingCall])

  // End active call
  const endCall = useCallback(async () => {
    if (activeCall) {
      const participants = activeCall.participants || []
      ws?.send(JSON.stringify({
        type: 'call_end',
        call_id: activeCall.id,
        recipients: participants,
      }))
      try { await api.post(`/calls/${activeCall.id}/end`) } catch (e) { /* ok */ }
    }
    cleanup()
  }, [activeCall, ws, cleanup])

  // Handle call accepted by remote
  const handleCallAccepted = useCallback(async (data) => {
    if (data.call_id !== activeCall?.id) return
    setCallStatus('active')

    // Create offer to the peer who accepted
    const pc = createPeerConnection(data.from_user)
    const offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    ws?.send(JSON.stringify({
      type: 'call_signal',
      call_id: data.call_id,
      signal_type: 'offer',
      signal: offer,
      recipients: [data.from_user],
    }))
  }, [activeCall, ws, setCallStatus, createPeerConnection])

  // Handle call ended by remote
  const handleCallEnded = useCallback(() => {
    cleanup()
    toast('Звонок завершён', { icon: '📞' })
  }, [cleanup])

  // Handle call rejected
  const handleCallRejected = useCallback(() => {
    cleanup()
    toast.error('Звонок отклонён')
  }, [cleanup])

  // Screen sharing
  const toggleScreenShare = useCallback(async () => {
    if (isScreenSharing) {
      // Switch back to camera
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: activeCall?.type === 'video' })
      setLocalStream(stream)
      setScreenSharing(false)
      // Replace tracks in peer connections
      Object.values(peerConnections).forEach(pc => {
        const sender = pc.getSenders().find(s => s.track?.kind === 'video')
        if (sender && stream.getVideoTracks()[0]) {
          sender.replaceTrack(stream.getVideoTracks()[0])
        }
      })
    } else {
      try {
        const screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false })
        const videoTrack = screenStream.getVideoTracks()[0]
        videoTrack.onended = () => toggleScreenShare()

        // Keep audio from localStream
        const newStream = new MediaStream([
          ...localStream.getAudioTracks(),
          videoTrack
        ])
        setLocalStream(newStream)
        setScreenSharing(true)

        // Replace video track in connections
        Object.values(peerConnections).forEach(pc => {
          const sender = pc.getSenders().find(s => s.track?.kind === 'video')
          if (sender) sender.replaceTrack(videoTrack)
        })
      } catch (e) {
        // User cancelled screen share picker
      }
    }
  }, [isScreenSharing, activeCall, localStream, peerConnections, setLocalStream, setScreenSharing])

  // Expose handlers for WebSocket events
  useEffect(() => {
    // Set up global call event handler
    window.__callHandlers = {
      handleSignal,
      handleCallAccepted,
      handleCallEnded,
      handleCallRejected,
    }
    return () => { delete window.__callHandlers }
  }, [handleSignal, handleCallAccepted, handleCallEnded, handleCallRejected])

  // Expose startCall globally so other components can use it
  useEffect(() => {
    window.__startCall = startCall
    return () => { delete window.__startCall }
  }, [startCall])

  const formatTime = (sec) => `${Math.floor(sec / 60).toString().padStart(2, '0')}:${(sec % 60).toString().padStart(2, '0')}`

  // Incoming call UI
  if (incomingCall) {
    return (
      <div className="fixed inset-0 z-[100] bg-black/70 flex items-center justify-center">
        <div className="bg-dark-900 border border-dark-700 rounded-3xl p-8 text-center shadow-2xl max-w-sm w-full animate-pulse-slow">
          <div className="w-20 h-20 rounded-full bg-dark-700 mx-auto mb-4 flex items-center justify-center overflow-hidden">
            {incomingCall.from_avatar ? (
              <img src={incomingCall.from_avatar} className="w-full h-full object-cover" />
            ) : (
              <span className="text-2xl text-white font-bold">{incomingCall.from_name?.[0] || '?'}</span>
            )}
          </div>
          <h3 className="text-white text-lg font-bold mb-1">{incomingCall.from_name || 'Неизвестный'}</h3>
          <p className="text-dark-400 text-sm mb-6">
            {incomingCall.call_type === 'video' ? 'Видеозвонок...' : 'Аудиозвонок...'}
          </p>
          <div className="flex items-center justify-center gap-6">
            <button onClick={rejectCall} className="w-14 h-14 rounded-full bg-red-600 hover:bg-red-700 flex items-center justify-center text-white transition-colors shadow-lg">
              <PhoneOff size={24} />
            </button>
            <button onClick={acceptCall} className="w-14 h-14 rounded-full bg-green-600 hover:bg-green-700 flex items-center justify-center text-white transition-colors shadow-lg">
              <Phone size={24} />
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Active call / ringing UI
  if (!activeCall) return null

  const isVideo = activeCall.type === 'video'
  const remoteStreamEntries = Object.entries(remoteStreams)

  return (
    <div className="fixed inset-0 z-[100] bg-dark-950 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4">
        <div>
          <h3 className="text-white font-bold text-sm">
            {callStatus === 'ringing' ? 'Вызов...' : callStatus === 'connecting' ? 'Подключение...' : 'Звонок'}
          </h3>
          {callStatus === 'active' && (
            <span className="text-dark-400 text-xs">{formatTime(callDuration)}</span>
          )}
        </div>
        <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${isVideo ? 'bg-blue-600/20 text-blue-400' : 'bg-green-600/20 text-green-400'}`}>
          {isVideo ? 'Видео' : 'Аудио'}
        </span>
      </div>

      {/* Video area */}
      <div className="flex-1 relative flex items-center justify-center bg-dark-950">
        {/* Remote streams */}
        {remoteStreamEntries.length > 0 ? (
          <div className={`grid gap-2 w-full h-full p-4 ${remoteStreamEntries.length > 1 ? 'grid-cols-2' : 'grid-cols-1'}`}>
            {remoteStreamEntries.map(([peerId, stream]) => (
              <div key={peerId} className="relative rounded-2xl overflow-hidden bg-dark-800">
                <video
                  ref={el => { if (el) remoteVideoRefs.current[peerId] = el }}
                  autoPlay
                  playsInline
                  className="w-full h-full object-cover"
                />
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center">
            <div className="w-24 h-24 rounded-full bg-dark-800 mx-auto mb-4 flex items-center justify-center">
              <Phone size={36} className={`text-dark-400 ${callStatus === 'ringing' ? 'animate-bounce' : ''}`} />
            </div>
            <p className="text-dark-400 text-sm">
              {callStatus === 'ringing' ? 'Ожидание ответа...' : callStatus === 'connecting' ? 'Подключение...' : 'Звонок активен'}
            </p>
          </div>
        )}

        {/* Local video (picture-in-picture) */}
        {localStream && (isVideo || isScreenSharing) && (
          <div className="absolute bottom-4 right-4 w-40 h-28 rounded-xl overflow-hidden border-2 border-dark-600 shadow-xl bg-dark-900">
            <video ref={localVideoRef} autoPlay muted playsInline className="w-full h-full object-cover" />
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="flex items-center justify-center gap-4 py-6 px-4 bg-dark-900/80 border-t border-dark-800">
        <button onClick={toggleMute}
          className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${isMuted ? 'bg-red-600 text-white' : 'bg-dark-700 text-white hover:bg-dark-600'}`}
          title={isMuted ? 'Включить микрофон' : 'Выключить микрофон'}>
          {isMuted ? <MicOff size={20} /> : <Mic size={20} />}
        </button>

        {isVideo && (
          <button onClick={toggleCamera}
            className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${isCameraOff ? 'bg-red-600 text-white' : 'bg-dark-700 text-white hover:bg-dark-600'}`}
            title={isCameraOff ? 'Включить камеру' : 'Выключить камеру'}>
            {isCameraOff ? <VideoOff size={20} /> : <Video size={20} />}
          </button>
        )}

        <button onClick={toggleScreenShare}
          className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${isScreenSharing ? 'bg-blue-600 text-white' : 'bg-dark-700 text-white hover:bg-dark-600'}`}
          title={isScreenSharing ? 'Остановить демонстрацию' : 'Демонстрация экрана'}>
          {isScreenSharing ? <MonitorOff size={20} /> : <Monitor size={20} />}
        </button>

        <button onClick={endCall}
          className="w-14 h-14 rounded-full bg-red-600 hover:bg-red-700 flex items-center justify-center text-white transition-colors shadow-lg"
          title="Завершить звонок">
          <PhoneOff size={22} />
        </button>
      </div>
    </div>
  )
}
