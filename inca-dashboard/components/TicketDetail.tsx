'use client'

import { ClaimTicket } from '@/types/claim'

interface Props {
  ticket: ClaimTicket
  onBack: () => void
}

export default function TicketDetail({ ticket, onBack }: Props) {
  return (
    <div style={{ padding: '32px', maxWidth: '800px' }}>
      {/* Back button */}
      <button
        onClick={onBack}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          fontFamily: 'var(--font-inter)',
          fontWeight: 500,
          fontSize: '14px',
          color: '#3F72AF',
          cursor: 'pointer',
          background: 'none',
          border: 'none',
          padding: 0,
          marginBottom: '24px',
        }}
      >
        ← Back to all claims
      </button>

      {/* Claim header */}
      <div style={{ marginBottom: '28px' }}>
        <h1
          style={{
            fontFamily: 'var(--font-syne)',
            fontWeight: 700,
            fontSize: '28px',
            color: '#112D4E',
            lineHeight: 1.2,
            marginBottom: '6px',
          }}
        >
          {ticket.claimRef}
        </h1>
        <p
          style={{
            fontFamily: 'var(--font-inter)',
            fontWeight: 400,
            fontSize: '15px',
            color: '#3F72AF',
            marginBottom: '4px',
          }}
        >
          {ticket.callerName}&nbsp;&nbsp;·&nbsp;&nbsp;{ticket.callerPhone}
        </p>
        <p
          style={{
            fontFamily: 'var(--font-inter)',
            fontWeight: 400,
            fontSize: '14px',
            color: '#112D4E',
          }}
        >
          {ticket.date}&nbsp;&nbsp;·&nbsp;&nbsp;{ticket.duration}
        </p>
      </div>

      {/* Card 1 — Claim Summary */}
      <div
        style={{
          background: '#F9F7F7',
          border: '1px solid #DBE2EF',
          borderRadius: '8px',
          boxShadow: '0 2px 8px rgba(17,45,78,0.06)',
          marginBottom: '20px',
          overflow: 'hidden',
        }}
      >
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #DBE2EF' }}>
          <h2
            style={{
              fontFamily: 'var(--font-syne)',
              fontWeight: 600,
              fontSize: '16px',
              color: '#112D4E',
            }}
          >
            Claim Summary
          </h2>
        </div>

        <div>
          {ticket.fields.map((field, idx) => (
            <div
              key={field.key}
              style={{
                display: 'flex',
                alignItems: 'baseline',
                padding: '10px 20px',
                background: idx % 2 === 0 ? 'rgba(219,226,239,0.25)' : 'transparent',
              }}
            >
              <span
                style={{
                  fontFamily: 'var(--font-inter)',
                  fontWeight: 400,
                  fontSize: '13px',
                  color: '#3F72AF',
                  width: '160px',
                  flexShrink: 0,
                }}
              >
                {field.key}
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-inter)',
                  fontWeight: field.value ? 500 : 400,
                  fontSize: '14px',
                  color: field.value ? '#112D4E' : '#9bacc8',
                }}
              >
                {field.value ?? '—'}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Card 2 — Call Transcript */}
      <div
        style={{
          background: '#F9F7F7',
          border: '1px solid #DBE2EF',
          borderRadius: '8px',
          boxShadow: '0 2px 8px rgba(17,45,78,0.06)',
          overflow: 'hidden',
        }}
      >
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #DBE2EF' }}>
          <h2
            style={{
              fontFamily: 'var(--font-syne)',
              fontWeight: 600,
              fontSize: '16px',
              color: '#112D4E',
            }}
          >
            Call Transcript
          </h2>
        </div>

        <div style={{ maxHeight: '360px', overflowY: 'auto' }}>
          {ticket.messages.map((msg, idx) => (
            <div
              key={msg.id}
              style={{
                padding: '12px 16px',
                background: msg.role === 'agent' ? 'rgba(219,226,239,0.35)' : '#ffffff',
                borderBottom: idx < ticket.messages.length - 1
                  ? '1px solid rgba(219,226,239,0.5)'
                  : 'none',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '6px',
                }}
              >
                <span
                  style={{
                    fontFamily: 'var(--font-inter)',
                    fontWeight: 400,
                    fontSize: '11px',
                    color: '#F9F7F7',
                    background: msg.role === 'agent' ? '#3F72AF' : '#112D4E',
                    borderRadius: '999px',
                    padding: '2px 8px',
                    lineHeight: 1.4,
                  }}
                >
                  {msg.role === 'agent' ? 'Sarah' : 'Caller'}
                </span>
                <span
                  style={{
                    fontFamily: 'monospace',
                    fontWeight: 400,
                    fontSize: '11px',
                    color: '#3F72AF',
                  }}
                >
                  {msg.timestamp}
                </span>
              </div>
              <p
                style={{
                  fontFamily: 'var(--font-inter)',
                  fontWeight: 400,
                  fontSize: '14px',
                  color: '#112D4E',
                  lineHeight: 1.6,
                }}
              >
                {msg.text}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
