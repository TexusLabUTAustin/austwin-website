import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import styles from './OnePager.module.css'
import colabLogo from '../assets/colab_logo.png'
import utciSs from '../assets/UTCI_SS.png'
import mobiusSvg from '../assets/mobius.svg'

type NodeKey = 'data' | 'tools' | 'users' | 'decisions'

/** Tool URLs: replace `#` when links are ready. */
const NODE_PANEL: Record<
  NodeKey,
  {
    title: string
    subtitle: string
    accent: string
    links: { label: string; href: string }[]
  }
> = {
  data: {
    title: 'Data',
    subtitle: 'Urban datasets & streams',
    accent: '#60a5fa',
    links: [],
  },
  tools: {
    title: 'Tools',
    subtitle: 'Simulation & developer tools',
    accent: '#2a8fd4',
    links: [
      { label: 'Thermalscape', href: '/thermalscape' },
      { label: 'CoolPath', href: '/coolpath' },
    ],
  },
  users: {
    title: 'Users',
    subtitle: 'Who uses AusTwin',
    accent: '#1a3c8f',
    links: [],
  },
  decisions: {
    title: 'Decisions',
    subtitle: 'Outputs & planning tools',
    accent: '#38bdf8',
    links: [],
  },
}

const NODE_HOVER: Record<NodeKey, { blurb: string }> = {
  data: {
    blurb:
      'Multiscale urban datasets—imagery, LiDAR, IoT, BIM, weather, and canopy layers.',
  },
  tools: {
    blurb:
      'AI simulations: heat & comfort, routes, fire/smoke, SOLWEIG-GPU, and the austwin-py SDK.',
  },
  users: {
    blurb:
      'City planners, UT researchers, stakeholders, and teams who query scenarios in the twin.',
  },
  decisions: {
    blurb:
      'Scenario views, dashboards, policy planners, and reports from integrated outputs.',
  },
}

/** Must be ≥ longest panel transition in OnePager.module.css (close animation). */
const PANEL_EXIT_MS = 520

const HINT_WIDTH = 220
const HINT_HEIGHT_EST = 118
const VIEW_PAD = 10
const NODE_EXCLUSION = 14
const HINT_GAP = 12

type HintSide = 'below' | 'above' | 'east' | 'west'

const HINT_SIDE_PRIORITY: Record<NodeKey, HintSide[]> = {
  tools: ['below', 'above', 'west', 'east'],
  decisions: ['above', 'below', 'west', 'east'],
  users: ['east', 'west', 'below', 'above'],
  data: ['west', 'east', 'below', 'above'],
}

type Box = { left: number; top: number; right: number; bottom: number }

function boxLT(left: number, top: number, w: number, h: number): Box {
  return { left, top, right: left + w, bottom: top + h }
}

function intersects(a: Box, b: Box) {
  return !(a.right <= b.left || a.left >= b.right || a.bottom <= b.top || a.top >= b.bottom)
}

function expandRect(r: DOMRect, m: number): Box {
  return {
    left: r.left - m,
    top: r.top - m,
    right: r.right + m,
    bottom: r.bottom + m,
  }
}

function clampToViewport(
  left: number,
  top: number,
  w: number,
  h: number,
): { left: number; top: number } {
  const vw = window.innerWidth
  const vh = window.innerHeight
  return {
    left: Math.round(
      Math.min(Math.max(VIEW_PAD, left), Math.max(VIEW_PAD, vw - w - VIEW_PAD)),
    ),
    top: Math.round(
      Math.min(Math.max(VIEW_PAD, top), Math.max(VIEW_PAD, vh - h - VIEW_PAD)),
    ),
  }
}

function rawCoordsForSide(
  side: HintSide,
  anchor: DOMRect,
  w: number,
  h: number,
  gap: number,
) {
  switch (side) {
    case 'below':
      return {
        left: anchor.left + anchor.width / 2 - w / 2,
        top: anchor.bottom + gap,
      }
    case 'above':
      return {
        left: anchor.left + anchor.width / 2 - w / 2,
        top: anchor.top - gap - h,
      }
    case 'east':
      return {
        left: anchor.right + gap,
        top: anchor.top + anchor.height / 2 - h / 2,
      }
    case 'west':
      return {
        left: anchor.left - gap - w,
        top: anchor.top + anchor.height / 2 - h / 2,
      }
  }
}

function obstacleBoxesFromRefs(
  refs: Record<NodeKey, HTMLButtonElement | null>,
  exclude: NodeKey,
): Box[] {
  const out: Box[] = []
  for (const k of Object.keys(refs) as NodeKey[]) {
    if (k === exclude) continue
    const el = refs[k]
    if (!el) continue
    out.push(expandRect(el.getBoundingClientRect(), NODE_EXCLUSION))
  }
  return out
}

function chromeObstacleBoxes(root: HTMLElement | null): Box[] {
  if (!root) return []
  return Array.from(root.querySelectorAll('[data-diagram-obstacle]')).map(
    (el) => expandRect(el.getBoundingClientRect(), 8),
  )
}

function overlapsAnyHint(box: Box, obstacles: Box[]) {
  return obstacles.some((o) => intersects(box, o))
}

function overlapPenalty(box: Box, obstacles: Box[]) {
  let pen = 0
  for (const o of obstacles) {
    if (!intersects(box, o)) continue
    const ix1 = Math.max(box.left, o.left)
    const iy1 = Math.max(box.top, o.top)
    const ix2 = Math.min(box.right, o.right)
    const iy2 = Math.min(box.bottom, o.bottom)
    pen += (ix2 - ix1) * (iy2 - iy1)
  }
  return pen
}

function computeFloatingHintPosition(
  key: NodeKey,
  refs: Record<NodeKey, HTMLButtonElement | null>,
  diagramRoot: HTMLElement | null,
): { left: number; top: number } | null {
  const el = refs[key]
  if (!el) return null
  const anchor = el.getBoundingClientRect()
  const w = HINT_WIDTH
  const h = HINT_HEIGHT_EST
  const obstacles = [
    ...obstacleBoxesFromRefs(refs, key),
    ...chromeObstacleBoxes(diagramRoot),
  ]

  for (const side of HINT_SIDE_PRIORITY[key]) {
    const raw = rawCoordsForSide(side, anchor, w, h, HINT_GAP)
    const clamped = clampToViewport(raw.left, raw.top, w, h)
    const box = boxLT(clamped.left, clamped.top, w, h)
    if (!overlapsAnyHint(box, obstacles)) {
      return clamped
    }
  }

  const allSides: HintSide[] = ['below', 'above', 'east', 'west']
  let best: { left: number; top: number; score: number } | null = null
  for (const side of allSides) {
    const raw = rawCoordsForSide(side, anchor, w, h, HINT_GAP)
    const clamped = clampToViewport(raw.left, raw.top, w, h)
    const box = boxLT(clamped.left, clamped.top, w, h)
    const drift =
      Math.abs(clamped.left - raw.left) + Math.abs(clamped.top - raw.top)
    const score = overlapPenalty(box, obstacles) * 800 + drift
    if (!best || score < best.score) {
      best = { left: clamped.left, top: clamped.top, score }
    }
  }
  return best ? { left: best.left, top: best.top } : null
}

function MagnifyingGlassIcon() {
  return (
    <svg
      className={styles.iconSvg}
      width="40"
      height="40"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden
    >
      <circle cx="10" cy="10" r="6" stroke="#2a8fd4" strokeWidth="2" />
      <path
        d="M14.5 14.5 21 21"
        stroke="#2a8fd4"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  )
}

function TriangleUpIcon() {
  return (
    <svg
      className={styles.iconSvg}
      width="31"
      height="28"
      viewBox="0 0 22 20"
      aria-hidden
    >
      <path fill="#3a5d9a" d="M11 0 22 20H0L11 0Z" />
    </svg>
  )
}

function CheckRoundedSquareIcon() {
  return (
    <svg
      className={styles.iconSvg}
      width="40"
      height="40"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden
    >
      <rect
        x="3"
        y="3"
        width="18"
        height="18"
        rx="5"
        stroke="#2a8fd4"
        strokeWidth="2"
      />
      <path
        d="M7 12.5 10.5 16 17 9"
        stroke="#2a8fd4"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export default function AusTwinOnePager() {
  const [selectedNode, setSelectedNode] = useState<NodeKey | null>(null)
  const [closingKey, setClosingKey] = useState<NodeKey | null>(null)
  const [panelEntered, setPanelEntered] = useState(false)
  const skipEnterAnimation = useRef(false)
  const closeTimeoutRef = useRef<number | null>(null)

  const nodeRefs = useRef<Record<NodeKey, HTMLButtonElement | null>>({
    data: null,
    tools: null,
    users: null,
    decisions: null,
  })
  const floatingHintRef = useRef<HTMLDivElement | null>(null)
  const diagramCanvasRef = useRef<HTMLDivElement | null>(null)
  const [floatingHint, setFloatingHint] = useState<{
    key: NodeKey
    left: number
    top: number
  } | null>(null)

  const setNodeRef = useCallback((key: NodeKey) => (el: HTMLButtonElement | null) => {
    nodeRefs.current[key] = el
  }, [])

  const repositionFloatingHint = useCallback((key: NodeKey) => {
    requestAnimationFrame(() => {
      const pos = computeFloatingHintPosition(
        key,
        nodeRefs.current,
        diagramCanvasRef.current,
      )
      if (pos) setFloatingHint({ key, ...pos })
    })
  }, [])

  const clearFloatingHint = useCallback(() => {
    setFloatingHint(null)
  }, [])

  useLayoutEffect(() => {
    if (!floatingHint) return
    const el = floatingHintRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const vw = window.innerWidth
    const vh = window.innerHeight
    let { left, top } = floatingHint
    if (r.right > vw - VIEW_PAD) {
      left = Math.max(VIEW_PAD, Math.round(vw - VIEW_PAD - r.width))
    }
    if (r.left < VIEW_PAD) {
      left = VIEW_PAD
    }
    if (r.bottom > vh - VIEW_PAD) {
      top = Math.max(VIEW_PAD, Math.round(vh - VIEW_PAD - r.height))
    }
    if (r.top < VIEW_PAD) {
      top = VIEW_PAD
    }
    if (left !== floatingHint.left || top !== floatingHint.top) {
      setFloatingHint((prev) =>
        prev && prev.key === floatingHint.key ? { ...prev, left, top } : prev,
      )
    }
  }, [floatingHint])

  useEffect(() => {
    if (!floatingHint) return
    const key = floatingHint.key
    const sync = () => {
      const pos = computeFloatingHintPosition(
        key,
        nodeRefs.current,
        diagramCanvasRef.current,
      )
      if (pos) setFloatingHint({ key, ...pos })
    }
    window.addEventListener('scroll', sync, true)
    window.addEventListener('resize', sync)
    return () => {
      window.removeEventListener('scroll', sync, true)
      window.removeEventListener('resize', sync)
    }
  }, [floatingHint?.key])

  const contentKey = selectedNode ?? closingKey
  const panelMounted = contentKey !== null

  const diagramNodeProps = useCallback(
    (key: NodeKey) => ({
      ref: setNodeRef(key),
      onMouseEnter: () => {
        if (
          !window.matchMedia('(hover: hover) and (pointer: fine)').matches
        ) {
          return
        }
        repositionFloatingHint(key)
      },
      onMouseLeave: () => {
        if (
          !window.matchMedia('(hover: hover) and (pointer: fine)').matches
        ) {
          return
        }
        clearFloatingHint()
      },
      onFocus: () => repositionFloatingHint(key),
      onBlur: clearFloatingHint,
    }),
    [clearFloatingHint, repositionFloatingHint, setNodeRef],
  )

  useEffect(() => {
    if (closingKey) return
    if (!selectedNode) {
      setPanelEntered(false)
      return
    }
    if (skipEnterAnimation.current) {
      skipEnterAnimation.current = false
      return
    }
    setPanelEntered(false)
    const id = requestAnimationFrame(() => {
      requestAnimationFrame(() => setPanelEntered(true))
    })
    return () => cancelAnimationFrame(id)
  }, [selectedNode, closingKey])

  function handleNodeClick(key: NodeKey) {
    if (closeTimeoutRef.current !== null) {
      window.clearTimeout(closeTimeoutRef.current)
      closeTimeoutRef.current = null
    }

    if (selectedNode === key) {
      setClosingKey(key)
      setSelectedNode(null)
      setPanelEntered(false)
      closeTimeoutRef.current = window.setTimeout(() => {
        setClosingKey(null)
        closeTimeoutRef.current = null
      }, PANEL_EXIT_MS)
      return
    }

    const fullyClosed = selectedNode === null && closingKey === null
    setClosingKey(null)
    setSelectedNode(key)

    if (!fullyClosed) {
      skipEnterAnimation.current = true
      setPanelEntered(true)
    }
  }

  function handleCloseButton() {
    if (closeTimeoutRef.current !== null) {
      window.clearTimeout(closeTimeoutRef.current)
      closeTimeoutRef.current = null
    }
    if (selectedNode !== null) {
      setClosingKey(selectedNode)
      setSelectedNode(null)
      setPanelEntered(false)
      closeTimeoutRef.current = window.setTimeout(() => {
        setClosingKey(null)
        closeTimeoutRef.current = null
      }, PANEL_EXIT_MS)
    } else {
      setClosingKey(null)
      setPanelEntered(false)
    }
  }

  function nodeClass(
    key: NodeKey,
    position: 'top' | 'bottom' | 'left' | 'right',
  ) {
    const pos =
      position === 'top'
        ? styles.nodeTop
        : position === 'bottom'
          ? styles.nodeBottom
          : position === 'left'
            ? styles.nodeLeft
            : styles.nodeRight
    const variant =
      key === 'data'
        ? styles.nodeData
        : key === 'tools'
          ? styles.nodeTools
          : key === 'users'
            ? styles.nodeUsers
            : styles.nodeDecisions
    const active = selectedNode === key ? styles.nodeActive : ''
    return `${styles.node} ${variant} ${pos} ${active}`.trim()
  }

  const panelBody =
    contentKey && NODE_PANEL[contentKey] ? NODE_PANEL[contentKey] : null

  return (
    <div className={styles.wrapper}>
      <div className={styles.left}>
        <div className={styles.brandRow}>
          <div className={styles.brandLeft}>
            <img
              src={colabLogo}
              alt="UT-City CoLab"
              className={styles.colabLogo}
              decoding="async"
            />
          </div>
          <div className={styles.brandDivider} aria-hidden />
          <span className={styles.texusLabel}>TE(x)US LAB</span>
        </div>

        <h1 className={styles.wordmark}>
          <span className={styles.wordmarkAus}>Aus</span>
          <span className={styles.wordmarkTwin}>Twin</span>
        </h1>

        <div className={styles.pill}>
          Austin Digital Twin{' '}
          <span className={styles.pillAccent}>Framework</span>
        </div>
        <p className={styles.body}>
          <strong>AusTwin is a digital twin framework</strong> for the City of
          Austin, Texas; a unified system that integrates{' '}
          <strong>AI tools, users, data-to-decision framework</strong> into a
          continuous loop designed to integrate infrastructure, shocks and
          stressors, and visualization and analysis of if-then scenarios.
        </p>
        <p className={styles.body}>
          <strong>AusTwin</strong> is led by the University of Texas{' '}
          <strong>
            Extreme Weather and Urban Sustainability (TExUS) Lab
          </strong>{' '}
          at Jackson School of Geosciences in close coordination with the{' '}
          <strong>UT-City CoLab.</strong>
        </p>

        <hr className={styles.sectionDivider} />

        <div className={`${styles.pill} ${styles.section2}`}>
          The Problem AusTwin <span className={styles.pillAccent}>Solves</span>
        </div>
        <p className={styles.body}>
          Cities increasingly have access to data, but{' '}
          <strong>the data-to-decision link is complex.</strong> Data is needed
          at user-desired scales, resolution, attributes, and with a
          visualization and quick if-then query capabilities.
        </p>
        <p className={styles.body}>
          AusTwin is built around the idea that{' '}
          <strong>AI and multiscale data can help close this gap</strong> with
          active engagement of endusers. AusTwin is a framework where AI tools,
          multiscale data, users, visualization, and decisions are part of the
          digital twin.
        </p>
      </div>

      <div className={styles.right}>
        <div className={styles.rightSection}>
          <p className={styles.interactiveHint}>
            Click the nodes to view links!
          </p>
          <div className={styles.diagramWrapper}>
            <div
              ref={diagramCanvasRef}
              className={styles.canvas}
              aria-label="AusTwin diagram"
            >
              <div className={styles.mobiusLayer} aria-hidden>
                <img
                  src={mobiusSvg}
                  alt=""
                  className={styles.mobiusGraphic}
                  decoding="async"
                />
              </div>

              <span
                className={`${styles.orbitLabel} ${styles.orbitLabelTop}`}
                data-diagram-obstacle
              >
                TOOLS
              </span>
              <span
                className={`${styles.orbitLabel} ${styles.orbitLabelLeft}`}
                data-diagram-obstacle
              >
                USERS
              </span>
              <span
                className={`${styles.orbitLabel} ${styles.orbitLabelRight}`}
                data-diagram-obstacle
              >
                DATA
              </span>
              <span
                className={`${styles.orbitLabel} ${styles.orbitLabelBottom}`}
                data-diagram-obstacle
              >
                DECISIONS
              </span>

              <div className={styles.nodesLayer}>
                <div className={styles.nodesCross}>
                  <button
                    type="button"
                    className={nodeClass('tools', 'top')}
                    {...diagramNodeProps('tools')}
                    onClick={() => handleNodeClick('tools')}
                    aria-pressed={selectedNode === 'tools'}
                    aria-expanded={panelMounted && contentKey === 'tools'}
                  >
                    <div className={styles.nodeToolsMedia}>
                      <img
                        src={utciSs}
                        alt="UTCI thermal comfort map"
                        className={styles.nodeToolsImg}
                        decoding="async"
                      />
                    </div>
                  </button>
                  <button
                    type="button"
                    className={nodeClass('decisions', 'bottom')}
                    {...diagramNodeProps('decisions')}
                    onClick={() => handleNodeClick('decisions')}
                    aria-pressed={selectedNode === 'decisions'}
                    aria-expanded={
                      panelMounted && contentKey === 'decisions'
                    }
                  >
                    <CheckRoundedSquareIcon />
                  </button>
                  <button
                    type="button"
                    className={nodeClass('users', 'left')}
                    {...diagramNodeProps('users')}
                    onClick={() => handleNodeClick('users')}
                    aria-pressed={selectedNode === 'users'}
                    aria-expanded={panelMounted && contentKey === 'users'}
                  >
                    <TriangleUpIcon />
                  </button>
                  <button
                    type="button"
                    className={nodeClass('data', 'right')}
                    {...diagramNodeProps('data')}
                    onClick={() => handleNodeClick('data')}
                    aria-pressed={selectedNode === 'data'}
                    aria-expanded={panelMounted && contentKey === 'data'}
                  >
                    <MagnifyingGlassIcon />
                  </button>
                </div>
              </div>
            </div>
          </div>

          {panelMounted && panelBody && (
            <aside
              className={`${styles.nodePanel} ${panelEntered ? styles.nodePanelVisible : ''}`}
              aria-label={
                panelBody.links.length > 0
                  ? `${panelBody.title} links`
                  : `${panelBody.title} panel`
              }
            >
              <div className={styles.nodePanelHeader}>
                <button
                  type="button"
                  className={styles.nodePanelClose}
                  onClick={handleCloseButton}
                  aria-label="Close panel"
                >
                  ×
                </button>
                <h2 className={styles.nodePanelTitle}>{panelBody.title}</h2>
                <p className={styles.nodePanelSubtitle}>
                  {panelBody.subtitle}
                </p>
              </div>
              <hr className={styles.nodePanelDivider} />
              {panelBody.links.length > 0 ? (
                <nav
                  className={styles.nodePanelLinks}
                  aria-label="Resource links"
                >
                  {panelBody.links.map((link) => {
                    const row = (
                      <>
                        <span
                          className={styles.panelLinkDot}
                          style={{ backgroundColor: panelBody.accent }}
                          aria-hidden
                        />
                        <span className={styles.panelLinkText}>
                          {link.label}
                        </span>
                        <span className={styles.panelLinkArrow} aria-hidden>
                          →
                        </span>
                      </>
                    )
                    const isAppPath =
                      link.href.startsWith('/') && link.href !== '#'
                    if (isAppPath) {
                      return (
                        <Link
                          key={link.label}
                          to={link.href}
                          className={styles.panelLink}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {row}
                        </Link>
                      )
                    }
                    return (
                      <a
                        key={link.label}
                        href={link.href}
                        className={styles.panelLink}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {row}
                      </a>
                    )
                  })}
                </nav>
              ) : (
                <p className={styles.panelComingSoon}>Coming soon</p>
              )}
            </aside>
          )}
        </div>
      </div>

      {floatingHint && (
        <div
          ref={floatingHintRef}
          className={styles.nodeHoverFloating}
          style={{
            left: floatingHint.left,
            top: floatingHint.top,
          }}
          aria-hidden
        >
          <span className={styles.nodeHoverText}>
            {NODE_HOVER[floatingHint.key].blurb}
          </span>
          <span className={styles.nodeHoverCta}>Click to know more</span>
        </div>
      )}
    </div>
  )
}
