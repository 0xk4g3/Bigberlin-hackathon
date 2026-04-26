'use client'

import { useState, useRef } from 'react'
import { ClaimTicket } from '@/types/claim'

const SIM_POOL: Omit<ClaimTicket, 'id'>[] = [
  {
    claimRef: 'INCA-2025-0350',
    callerName: 'Laura Schneider',
    callerPhone: '+49 30 9876 5432',
    date: 'Apr 25, 2025',
    duration: '06:14',
    lossType: 'Side-swipe collision',
    location: 'Kudamm, Berlin',
    fields: [
      { key: 'Date',            value: '2025-04-25 ~16:45' },
      { key: 'Location',        value: 'Kurfürstendamm, Charlottenburg' },
      { key: 'Loss type',       value: 'Side-swipe collision' },
      { key: '3rd party plate', value: 'B-LK 9921' },
      { key: 'Police report',   value: null },
      { key: 'Injuries',        value: 'None' },
      { key: 'Drivable',        value: 'Yes' },
      { key: 'Policy no.',      value: 'POL-3310-DE' },
      { key: 'Driver scope',    value: 'Policyholder' },
      { key: 'Repair shop',     value: null },
    ],
    messages: [
      { id: '1', role: 'agent',  text: 'Thank you for calling INCA claims. This is Klaus. Are you safe?', timestamp: '00:00:05' },
      { id: '2', role: 'caller', text: 'Yes. A car sideswiped me on the Kudamm. I have their plate.', timestamp: '00:00:20' },
      { id: '3', role: 'agent',  text: 'Got it. Is the vehicle still drivable?', timestamp: '00:00:35' },
      { id: '4', role: 'caller', text: 'Yes, I drove to a side street. The damage is on the left door.', timestamp: '00:00:58' },
    ],
  },
  {
    claimRef: 'INCA-2025-0351',
    callerName: 'Fatima Al-Rashid',
    callerPhone: '+49 160 4443322',
    date: 'Apr 25, 2025',
    duration: '04:55',
    lossType: 'Hail damage',
    location: 'Prenzlauer Berg, Berlin',
    fields: [
      { key: 'Date',            value: '2025-04-25 ~13:00' },
      { key: 'Location',        value: 'Prenzlauer Berg, Berlin' },
      { key: 'Loss type',       value: 'Hail damage' },
      { key: '3rd party plate', value: null },
      { key: 'Police report',   value: null },
      { key: 'Injuries',        value: 'None' },
      { key: 'Drivable',        value: 'Yes' },
      { key: 'Policy no.',      value: 'POL-7721-DE' },
      { key: 'Driver scope',    value: 'Policyholder' },
      { key: 'Repair shop',     value: 'Karosserie Nord' },
    ],
    messages: [
      { id: '1', role: 'agent',  text: 'Thank you for calling INCA claims. This is Klaus. How can I help you today?', timestamp: '00:00:06' },
      { id: '2', role: 'caller', text: 'My car was caught in a hailstorm and the roof and hood are badly dented.', timestamp: '00:00:22' },
      { id: '3', role: 'agent',  text: 'I am sorry to hear that. Do you have a preferred repair shop?', timestamp: '00:00:38' },
      { id: '4', role: 'caller', text: 'Yes — Karosserie Nord in Pankow.', timestamp: '00:00:55' },
    ],
  },
  {
    claimRef: 'INCA-2025-0352',
    callerName: 'Erik Brandt',
    callerPhone: '+49 176 1122334',
    date: 'Apr 25, 2025',
    duration: '03:22',
    lossType: 'Theft — catalytic converter',
    location: 'Neukölln, Berlin',
    fields: [
      { key: 'Date',            value: '2025-04-25 ~03:00' },
      { key: 'Location',        value: 'Karl-Marx-Straße, Neukölln' },
      { key: 'Loss type',       value: 'Theft — catalytic converter' },
      { key: '3rd party plate', value: null },
      { key: 'Police report',   value: 'BP-2025-04-25-0588' },
      { key: 'Injuries',        value: 'None' },
      { key: 'Drivable',        value: 'No — towed' },
      { key: 'Policy no.',      value: 'POL-5540-DE' },
      { key: 'Driver scope',    value: 'Policyholder' },
      { key: 'Repair shop',     value: null },
    ],
    messages: [
      { id: '1', role: 'agent',  text: 'Thank you for calling INCA claims. This is Klaus. Are you safe?', timestamp: '00:00:04' },
      { id: '2', role: 'caller', text: 'Yes. I went to my car this morning and someone stole the catalytic converter.', timestamp: '00:00:18' },
      { id: '3', role: 'agent',  text: 'I am sorry. Did you file a police report?', timestamp: '00:00:30' },
      { id: '4', role: 'caller', text: 'Yes, case BP-2025-04-25-0588.', timestamp: '00:00:44' },
    ],
  },
  {
    claimRef: 'INCA-2025-0353',
    callerName: 'Sophie Richter',
    callerPhone: '+49 151 7788990',
    date: 'Apr 25, 2025',
    duration: '05:40',
    lossType: 'Flood damage',
    location: 'Spandau, Berlin',
    fields: [
      { key: 'Date',            value: '2025-04-25 ~08:30' },
      { key: 'Location',        value: 'Spandau, Berlin' },
      { key: 'Loss type',       value: 'Flood damage' },
      { key: '3rd party plate', value: null },
      { key: 'Police report',   value: null },
      { key: 'Injuries',        value: 'None' },
      { key: 'Drivable',        value: 'No — total loss suspected' },
      { key: 'Policy no.',      value: 'POL-8832-DE' },
      { key: 'Driver scope',    value: 'Policyholder' },
      { key: 'Repair shop',     value: 'West Auto Spandau' },
    ],
    messages: [
      { id: '1', role: 'agent',  text: 'Thank you for calling INCA claims. This is Klaus. What happened?', timestamp: '00:00:07' },
      { id: '2', role: 'caller', text: 'My car was parked in an underground garage that flooded overnight.', timestamp: '00:00:25' },
      { id: '3', role: 'agent',  text: 'That sounds very serious. Is the vehicle still in the garage?', timestamp: '00:00:40' },
      { id: '4', role: 'caller', text: 'No it was towed to West Auto Spandau this morning.', timestamp: '00:01:02' },
    ],
  },
]

interface Props {
  onSimulate: (ticket: ClaimTicket) => void
}

export default function SimulatorButton({ onSimulate }: Props) {
  const [open, setOpen] = useState(false)
  const [firing, setFiring] = useState(false)
  const [lastFired, setLastFired] = useState<string | null>(null)
  const indexRef = useRef(0)

  function fire() {
    if (firing) return
    const template = SIM_POOL[indexRef.current % SIM_POOL.length]
    indexRef.current += 1
    const ticket: ClaimTicket = { ...template, id: `sim-${Date.now()}` }
    setFiring(true)
    setLastFired(ticket.callerName)
    onSimulate(ticket)
    setTimeout(() => setFiring(false), 1200)
  }

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        zIndex: 200,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-end',
        gap: '10px',
      }}
    >
      {/* Expanded panel */}
      {open && (
        <div
          style={{
            background: '#F9F7F7',
            border: '1px solid #DBE2EF',
            borderRadius: '12px',
            boxShadow: '0 8px 32px rgba(17,45,78,0.14)',
            padding: '16px 18px',
            width: '260px',
          }}
        >
          <div
            style={{
              fontFamily: 'var(--font-syne)',
              fontWeight: 600,
              fontSize: '13px',
              color: '#112D4E',
              marginBottom: '4px',
            }}
          >
            Call Simulator
          </div>
          <div
            style={{
              fontFamily: 'var(--font-inter)',
              fontWeight: 400,
              fontSize: '12px',
              color: '#3F72AF',
              marginBottom: '14px',
              lineHeight: 1.5,
            }}
          >
            Fires a fake <code style={{ fontFamily: 'monospace', fontSize: '11px' }}>call_ended</code> event — triggers notification, sound &amp; card fade-in.
          </div>

          {/* Last fired */}
          {lastFired && (
            <div
              style={{
                background: 'rgba(63,114,175,0.08)',
                border: '1px solid rgba(63,114,175,0.2)',
                borderRadius: '6px',
                padding: '7px 10px',
                marginBottom: '12px',
                fontFamily: 'var(--font-inter)',
                fontSize: '12px',
                color: '#3F72AF',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <span style={{ fontSize: '14px' }}>✓</span>
              <span>Last: <strong style={{ color: '#112D4E' }}>{lastFired}</strong></span>
            </div>
          )}

          <button
            onClick={fire}
            disabled={firing}
            style={{
              width: '100%',
              background: firing ? '#DBE2EF' : '#3F72AF',
              color: firing ? '#3F72AF' : '#F9F7F7',
              border: 'none',
              borderRadius: '8px',
              padding: '10px 0',
              fontFamily: 'var(--font-inter)',
              fontWeight: 500,
              fontSize: '13px',
              cursor: firing ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              transition: 'all 0.2s ease',
            }}
          >
            {/* Phone hang-up icon */}
            <svg
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{
                transform: 'rotate(135deg)',
                transition: 'transform 0.3s ease',
              }}
            >
              <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.9 12a19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 3.81 1h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 8.91a16 16 0 0 0 6 6l.95-.95a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
            </svg>
            {firing ? 'Firing…' : 'Simulate Call End'}
          </button>

          <div
            style={{
              fontFamily: 'var(--font-inter)',
              fontWeight: 400,
              fontSize: '11px',
              color: '#9bacc8',
              marginTop: '8px',
              textAlign: 'center',
            }}
          >
            {SIM_POOL.length} callers in pool · #{(indexRef.current % SIM_POOL.length) + 1} next
          </div>
        </div>
      )}

      {/* Toggle FAB */}
      <button
        onClick={() => setOpen((v) => !v)}
        title={open ? 'Close simulator' : 'Open call simulator'}
        style={{
          width: '48px',
          height: '48px',
          borderRadius: '50%',
          background: open ? '#112D4E' : '#3F72AF',
          border: 'none',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 4px 16px rgba(17,45,78,0.25)',
          transition: 'background 0.2s ease, transform 0.2s ease',
          color: '#F9F7F7',
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.transform = 'scale(1.08)'
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.transform = 'scale(1)'
        }}
      >
        {open ? (
          /* × close */
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        ) : (
          /* play / bolt icon */
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
          </svg>
        )}
      </button>
    </div>
  )
}
