'use client'

import { useState } from 'react'

export default function Sidebar({ count }: { count: number }) {
  const [open, setOpen] = useState(true)

  return (
    <aside
      style={{
        width: open ? '240px' : '56px',
        height: '100vh',
        flexShrink: 0,
        background: '#DBE2EF',
        padding: open ? '24px 16px' : '24px 10px',
        display: 'flex',
        flexDirection: 'column',
        position: 'sticky',
        top: 0,
        transition: 'width 0.25s ease, padding 0.25s ease',
        overflow: 'hidden',
      }}
    >
      {/* Top row: title + toggle */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: open ? 'space-between' : 'center',
          minHeight: '28px',
        }}
      >
        {open && (
          <span
            style={{
              fontFamily: 'var(--font-syne)',
              fontWeight: 700,
              fontSize: '18px',
              color: '#112D4E',
              letterSpacing: '-0.01em',
              whiteSpace: 'nowrap',
            }}
          >
            INCA Claims
          </span>
        )}

        <button
          onClick={() => setOpen((v) => !v)}
          title={open ? 'Collapse sidebar' : 'Expand sidebar'}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            padding: '4px',
            borderRadius: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#3F72AF',
            flexShrink: 0,
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = 'rgba(63,114,175,0.12)'
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = 'none'
          }}
        >
          {/* Chevron icon — points left when open, right when closed */}
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{
              transition: 'transform 0.25s ease',
              transform: open ? 'rotate(0deg)' : 'rotate(180deg)',
            }}
          >
            <polyline points="15 18 9 12 15 6" />
          </svg>
        </button>
      </div>

      {/* Divider */}
      <div
        style={{
          height: '1px',
          background: 'rgba(63,114,175,0.2)',
          margin: '12px 0',
        }}
      />

      {/* Nav item */}
      <nav>
        {open ? (
          /* Expanded state */
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              background: '#F9F7F7',
              borderLeft: '3px solid #3F72AF',
              borderRadius: '0 6px 6px 0',
              padding: '10px 12px',
            }}
          >
            <ClipboardIcon />
            <span
              style={{
                fontFamily: 'var(--font-inter)',
                fontWeight: 500,
                fontSize: '14px',
                color: '#112D4E',
                flex: 1,
                whiteSpace: 'nowrap',
              }}
            >
              Claimed Insurance
            </span>
            <span
              style={{
                background: '#3F72AF',
                color: '#F9F7F7',
                borderRadius: '999px',
                fontSize: '11px',
                padding: '2px 8px',
                fontFamily: 'var(--font-inter)',
                fontWeight: 400,
                lineHeight: 1.4,
              }}
            >
              {count}
            </span>
          </div>
        ) : (
          /* Collapsed state — icon only with count dot */
          <div
            style={{
              position: 'relative',
              display: 'flex',
              justifyContent: 'center',
              background: '#F9F7F7',
              borderLeft: '3px solid #3F72AF',
              borderRadius: '0 6px 6px 0',
              padding: '10px 8px',
            }}
            title="Claimed Insurance"
          >
            <ClipboardIcon />
            <span
              style={{
                position: 'absolute',
                top: '4px',
                right: '4px',
                background: '#3F72AF',
                color: '#F9F7F7',
                borderRadius: '999px',
                fontSize: '9px',
                padding: '1px 4px',
                fontFamily: 'var(--font-inter)',
                fontWeight: 400,
                lineHeight: 1.4,
              }}
            >
              {count}
            </span>
          </div>
        )}
      </nav>
    </aside>
  )
}

function ClipboardIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#112D4E"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ flexShrink: 0 }}
    >
      <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
      <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
    </svg>
  )
}
