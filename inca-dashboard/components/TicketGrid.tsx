'use client'

import { useEffect, useRef, useState } from 'react'
import { ClaimTicket } from '@/types/claim'
import TicketCard from './TicketCard'

interface Props {
  tickets: ClaimTicket[]
  onSelect: (ticket: ClaimTicket) => void
  newIds: Set<string>
  unreadCount: number
  onClearNotifications: () => void
}

export default function TicketGrid({
  tickets,
  onSelect,
  newIds,
  unreadCount,
  onClearNotifications,
}: Props) {
  const bellRef = useRef<SVGSVGElement>(null)
  const badgeRef = useRef<HTMLSpanElement>(null)
  const prevUnread = useRef(0)
  const [panelOpen, setPanelOpen] = useState(false)

  useEffect(() => {
    if (unreadCount > prevUnread.current) {
      // ring the bell
      if (bellRef.current) {
        bellRef.current.classList.remove('bell-ring')
        void (bellRef.current as unknown as HTMLElement).offsetWidth
        bellRef.current.classList.add('bell-ring')
      }
      // pop the badge
      if (badgeRef.current) {
        badgeRef.current.classList.remove('badge-pop')
        void badgeRef.current.offsetWidth
        badgeRef.current.classList.add('badge-pop')
      }
    }
    prevUnread.current = unreadCount
  }, [unreadCount])

  const handleBellClick = () => {
    setPanelOpen((v) => !v)
    if (!panelOpen) onClearNotifications()
  }

  return (
    <div style={{ padding: '32px' }}>
      {/* Header row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          marginBottom: '24px',
        }}
      >
        <div>
          <h1
            style={{
              fontFamily: 'var(--font-syne)',
              fontWeight: 700,
              fontSize: '24px',
              color: '#112D4E',
              lineHeight: 1.2,
            }}
          >
            Claimed Insurance
          </h1>
          <p
            style={{
              fontFamily: 'var(--font-inter)',
              fontWeight: 400,
              fontSize: '14px',
              color: '#3F72AF',
              marginTop: '4px',
            }}
          >
            {tickets.length} completed call{tickets.length !== 1 ? 's' : ''}
          </p>
        </div>

        {/* Bell button */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={handleBellClick}
            title="Notifications"
            style={{
              background: unreadCount > 0 ? 'rgba(63,114,175,0.1)' : 'none',
              border: '1px solid',
              borderColor: unreadCount > 0 ? '#3F72AF' : '#DBE2EF',
              borderRadius: '10px',
              cursor: 'pointer',
              padding: '8px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s ease',
              position: 'relative',
            }}
            onMouseEnter={(e) => {
              const el = e.currentTarget as HTMLButtonElement
              el.style.background = 'rgba(63,114,175,0.12)'
              el.style.borderColor = '#3F72AF'
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget as HTMLButtonElement
              el.style.background = unreadCount > 0 ? 'rgba(63,114,175,0.1)' : 'none'
              el.style.borderColor = unreadCount > 0 ? '#3F72AF' : '#DBE2EF'
            }}
          >
            <svg
              ref={bellRef}
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke={unreadCount > 0 ? '#3F72AF' : '#112D4E'}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
              <path d="M13.73 21a2 2 0 0 1-3.46 0" />
            </svg>

            {/* Unread badge */}
            {unreadCount > 0 && (
              <span
                ref={badgeRef}
                className="badge-pop"
                style={{
                  position: 'absolute',
                  top: '-6px',
                  right: '-6px',
                  background: '#3F72AF',
                  color: '#F9F7F7',
                  borderRadius: '999px',
                  fontSize: '10px',
                  fontFamily: 'var(--font-inter)',
                  fontWeight: 500,
                  minWidth: '18px',
                  height: '18px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '0 4px',
                  border: '2px solid #F9F7F7',
                  lineHeight: 1,
                }}
              >
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </button>

          {/* Dropdown panel */}
          {panelOpen && (
            <div
              style={{
                position: 'absolute',
                top: 'calc(100% + 8px)',
                right: 0,
                width: '320px',
                background: '#F9F7F7',
                border: '1px solid #DBE2EF',
                borderRadius: '10px',
                boxShadow: '0 8px 24px rgba(17,45,78,0.12)',
                zIndex: 100,
                overflow: 'hidden',
              }}
            >
              {/* Panel header */}
              <div
                style={{
                  padding: '14px 16px',
                  borderBottom: '1px solid #DBE2EF',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <span
                  style={{
                    fontFamily: 'var(--font-syne)',
                    fontWeight: 600,
                    fontSize: '14px',
                    color: '#112D4E',
                  }}
                >
                  Notifications
                </span>
                <button
                  onClick={() => setPanelOpen(false)}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: '#3F72AF',
                    fontSize: '18px',
                    lineHeight: 1,
                    padding: '0 2px',
                  }}
                >
                  ×
                </button>
              </div>

              {/* Notification list — show most-recent new arrivals */}
              <div style={{ maxHeight: '320px', overflowY: 'auto' }}>
                {[...tickets]
                  .filter((t) => newIds.has(t.id) || tickets.indexOf(t) < 5)
                  .slice(0, 8)
                  .map((ticket, idx) => (
                    <div
                      key={ticket.id}
                      onClick={() => {
                        setPanelOpen(false)
                        onSelect(ticket)
                      }}
                      style={{
                        padding: '12px 16px',
                        borderBottom: idx < Math.min(tickets.length, 8) - 1
                          ? '1px solid rgba(219,226,239,0.5)'
                          : 'none',
                        cursor: 'pointer',
                        background: newIds.has(ticket.id)
                          ? 'rgba(63,114,175,0.07)'
                          : 'transparent',
                        transition: 'background 0.15s ease',
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: '10px',
                      }}
                      onMouseEnter={(e) => {
                        (e.currentTarget as HTMLDivElement).style.background =
                          'rgba(219,226,239,0.4)'
                      }}
                      onMouseLeave={(e) => {
                        (e.currentTarget as HTMLDivElement).style.background = newIds.has(
                          ticket.id
                        )
                          ? 'rgba(63,114,175,0.07)'
                          : 'transparent'
                      }}
                    >
                      {/* Dot indicator for new */}
                      <div
                        style={{
                          width: '7px',
                          height: '7px',
                          borderRadius: '50%',
                          background: newIds.has(ticket.id) ? '#3F72AF' : 'transparent',
                          marginTop: '5px',
                          flexShrink: 0,
                        }}
                      />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div
                          style={{
                            fontFamily: 'var(--font-inter)',
                            fontWeight: 500,
                            fontSize: '13px',
                            color: '#112D4E',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          {ticket.callerName}
                        </div>
                        <div
                          style={{
                            fontFamily: 'var(--font-inter)',
                            fontWeight: 400,
                            fontSize: '12px',
                            color: '#3F72AF',
                            marginTop: '2px',
                          }}
                        >
                          {ticket.claimRef} · {ticket.lossType}
                        </div>
                      </div>
                      <div
                        style={{
                          fontFamily: 'var(--font-inter)',
                          fontWeight: 400,
                          fontSize: '11px',
                          color: '#3F72AF',
                          flexShrink: 0,
                          marginTop: '2px',
                        }}
                      >
                        {ticket.date}
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Card grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
          gap: '20px',
        }}
      >
        {tickets.map((ticket) => (
          <TicketCard
            key={ticket.id}
            ticket={ticket}
            onSelect={onSelect}
            isNew={newIds.has(ticket.id)}
          />
        ))}
      </div>
    </div>
  )
}
