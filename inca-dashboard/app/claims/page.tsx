'use client'

import { useState, useEffect } from 'react'
import Sidebar from '@/components/Sidebar'
import TicketGrid from '@/components/TicketGrid'
import TicketDetail from '@/components/TicketDetail'
import SimulatorButton from '@/components/SimulatorButton'
import { ClaimTicket } from '@/types/claim'
import { MOCK_TICKETS } from '@/lib/mockData'
import { playNotificationChime } from '@/lib/notificationSound'

export default function ClaimsPage() {
  const [tickets, setTickets] = useState<ClaimTicket[]>(MOCK_TICKETS)
  const [selected, setSelected] = useState<ClaimTicket | null>(null)
  const [newIds, setNewIds] = useState<Set<string>>(new Set())
  const [unreadCount, setUnreadCount] = useState(0)

  function handleIncomingTicket(incoming: ClaimTicket) {
    setTickets((prev) => [incoming, ...prev])
    setUnreadCount((prev) => prev + 1)
    setNewIds((prev) => new Set(prev).add(incoming.id))
    playNotificationChime()
    setTimeout(() => {
      setNewIds((prev) => {
        const next = new Set(prev)
        next.delete(incoming.id)
        return next
      })
    }, 500)
  }

  useEffect(() => {
    const ws = new WebSocket(process.env.NEXT_PUBLIC_WS_URL ?? 'ws://localhost:8080/ws')
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'call_ended') {
        handleIncomingTicket(msg.data)
      }
    }
    ws.onerror = () => {}
    return () => ws.close()
  }, [])

  return (
    <div style={{ display: 'flex', height: '100vh', background: '#F9F7F7' }}>
      <Sidebar count={tickets.length} />
      <main style={{ flex: 1, overflowY: 'auto' }}>
        {selected ? (
          <TicketDetail ticket={selected} onBack={() => setSelected(null)} />
        ) : (
          <TicketGrid
            tickets={tickets}
            onSelect={setSelected}
            newIds={newIds}
            unreadCount={unreadCount}
            onClearNotifications={() => setUnreadCount(0)}
          />
        )}
      </main>

      <SimulatorButton onSimulate={handleIncomingTicket} />
    </div>
  )
}
