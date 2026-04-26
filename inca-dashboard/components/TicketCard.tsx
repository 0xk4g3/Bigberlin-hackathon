'use client'

import { ClaimTicket } from '@/types/claim'

interface Props {
  ticket: ClaimTicket
  onSelect: (ticket: ClaimTicket) => void
  isNew?: boolean
}

export default function TicketCard({ ticket, onSelect, isNew }: Props) {
  return (
    <div
      className={isNew ? 'fade-in' : ''}
      onClick={() => onSelect(ticket)}
      style={{
        background: '#F9F7F7',
        border: '1px solid #DBE2EF',
        borderRadius: '8px',
        boxShadow: '0 2px 8px rgba(17,45,78,0.08)',
        padding: '20px',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
      }}
      onMouseEnter={(e) => {
        const el = e.currentTarget as HTMLDivElement
        el.style.borderColor = '#3F72AF'
        el.style.boxShadow = '0 4px 16px rgba(17,45,78,0.14)'
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget as HTMLDivElement
        el.style.borderColor = '#DBE2EF'
        el.style.boxShadow = '0 2px 8px rgba(17,45,78,0.08)'
      }}
    >
      <div
        style={{
          fontFamily: 'var(--font-inter)',
          fontWeight: 500,
          fontSize: '12px',
          color: '#3F72AF',
          fontVariantNumeric: 'tabular-nums',
          fontFeatureSettings: '"tnum"',
          letterSpacing: '0.02em',
          marginBottom: '4px',
        }}
      >
        {ticket.claimRef}
      </div>

      <div
        style={{
          fontFamily: 'var(--font-syne)',
          fontWeight: 700,
          fontSize: '20px',
          color: '#112D4E',
          marginBottom: '4px',
          lineHeight: 1.2,
        }}
      >
        {ticket.callerName}
      </div>

      <div
        style={{
          fontFamily: 'var(--font-inter)',
          fontWeight: 400,
          fontSize: '13px',
          color: '#3F72AF',
          marginBottom: '12px',
        }}
      >
        {ticket.date}&nbsp;&nbsp;·&nbsp;&nbsp;{ticket.duration}
      </div>

      <div
        style={{
          height: '1px',
          background: '#DBE2EF',
          marginBottom: '12px',
        }}
      />

      <div
        style={{
          fontFamily: 'var(--font-inter)',
          fontWeight: 400,
          fontSize: '14px',
          color: '#112D4E',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {ticket.lossType}&nbsp;·&nbsp;{ticket.location}
      </div>
    </div>
  )
}
