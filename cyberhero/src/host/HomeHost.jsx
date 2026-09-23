import { useEffect, useRef, useState } from 'react'
import IoHost from './IoHost.jsx'

/* IO on the eLearning home page. The Flask template renders the path
   cards (`<a data-io-path="basic|kids">`); this component makes IO react
   to them - hover / focus gets a line about that door, choosing one gets
   a goodbye wave (the link itself navigates normally). */

// bigger IO on monitors, compact on phones (the sizes exist in io-host.css)
function stageSize() {
  if (typeof window === 'undefined') return 320
  if (window.innerWidth >= 1200) return 320
  if (window.innerWidth >= 576) return 230
  return 210
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

/* Wire every `[data-io-path]` element on the page to the host's ref. */
export function attachDoors(io, root = document) {
  const cards = Array.from(root.querySelectorAll('[data-io-path]'))
  const detach = cards.map((card) => {
    const kind = card.dataset.ioPath === 'kids' ? 'kids' : 'basic'
    const handlers = {
      mouseenter: () => io.current?.hover(kind, 'mouse'),
      mouseleave: () => io.current?.unhover('mouse'),
      focus: () => io.current?.hover(kind, 'focus'),
      blur: () => io.current?.unhover('focus'),
      click: () => io.current?.farewell(),
    }
    for (const [event, fn] of Object.entries(handlers)) card.addEventListener(event, fn)
    return () => {
      for (const [event, fn] of Object.entries(handlers)) card.removeEventListener(event, fn)
    }
  })
  return () => detach.forEach((off) => off())
}

export default function HomeHost({ lang = 'ka', skin = 'classic', label = '', doors = ['basic', 'kids'] }) {
  const io = useRef(null)
  const size = useStageSize()

  useEffect(() => attachDoors(io), [])

  return <IoHost ref={io} lang={lang} size={size} skin={skin} hintLabel={label} doors={doors} />
}
