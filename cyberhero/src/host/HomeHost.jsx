import { useEffect, useRef, useState } from 'react'
import IoHost from './IoHost.jsx'

/* IO on the eLearning home page: the floating corner widget (fixed, so he
   follows the visitor down the page, with the same close / reopen chip as
   on CyberHero). The Flask template tags two of its buttons as IO's "doors"
   (`<a data-io-path="basic|kids">`: Browse courses, Open CyberHero); this
   component makes IO react to them - hover / focus gets a line about that
   door, choosing one gets a goodbye wave (the link itself navigates
   normally). */

// the same sizes as the CyberHero widget (MascotWidget.jsx): bigger on
// monitors, compact on phones - all present in io-host.css
function stageSize() {
  if (typeof window === 'undefined') return 230
  if (window.innerWidth >= 1100) return 230
  if (window.innerWidth >= 720) return 185
  return 150
}

function useStageSize() {
  const [size, setSize] = useState(stageSize)
  useEffect(() => {
    const onResize = () => setSize(stageSize())
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  return size
}

/* a click that will actually leave the page (not a new-tab / context click) */
function isPlainClick(event) {
  return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey
}

/* Wire every `[data-io-path]` element on the page to the host's ref. */
export function attachDoors(io, root = document) {
  const doors = Array.from(root.querySelectorAll('[data-io-path]'))
  const detach = doors.map((door) => {
    const kind = door.dataset.ioPath === 'kids' ? 'kids' : 'basic'
    const handlers = {
      mouseenter: () => io.current?.hover(kind, 'mouse'),
      mouseleave: () => io.current?.unhover('mouse'),
      focus: () => io.current?.hover(kind, 'focus'),
      blur: () => io.current?.unhover('focus'),
      click: (event) => {
        if (isPlainClick(event)) io.current?.farewell()
      },
    }
    for (const [event, fn] of Object.entries(handlers)) door.addEventListener(event, fn)
    return () => {
      for (const [event, fn] of Object.entries(handlers)) door.removeEventListener(event, fn)
    }
  })
  return () => detach.forEach((off) => off())
}

export default function HomeHost({
  lang = 'ka',
  skin = 'classic',
  label = '',
  closeLabel = '',
  openLabel = '',
  doors = ['basic', 'kids'],
  signedIn = false,
}) {
  const io = useRef(null)
  const wrap = useRef(null)
  const chip = useRef(null)
  const size = useStageSize()
  const [open, setOpen] = useState(true)
  const toggled = useRef(false)

  // the doors keep working while he is hidden (the ref is simply empty)
  useEffect(() => attachDoors(io), [])

  // hiding / showing him must not drop keyboard focus on <body>: the chip
  // takes it when he goes, IO himself when he is back
  useEffect(() => {
    if (!toggled.current) return
    if (open) wrap.current?.querySelector('.mascot-canvas')?.focus()
    else chip.current?.focus()
  }, [open])
  const toggle = (next) => {
    toggled.current = true
    setOpen(next)
  }

  return (
    <div className="io-host-wrap" ref={wrap}>
      {open ? (
        <IoHost
          ref={io}
          lang={lang}
          size={size}
          skin={skin}
          hintLabel={label}
          closeLabel={closeLabel}
          doors={doors}
          signedIn={signedIn}
          onClose={() => toggle(false)}
        />
      ) : (
        <button type="button" className="io-host-chip" ref={chip} onClick={() => toggle(true)} aria-label={openLabel}>
          🤖
        </button>
      )}
    </div>
  )
}
