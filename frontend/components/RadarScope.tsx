"use client";

import { useEffect, useState } from "react";
import { fetchPapers } from "@/lib/api";
import type { PaperListItem } from "@/lib/types";

const CX = 320;
const CY = 200;
const R_OUT = 190;

const SPOKE_ANGLES = Array.from({ length: 12 }, (_, i) => i * 30);
const TICK_ANGLES = Array.from({ length: 36 }, (_, i) => i * 10);

function polar(deg: number, radius: number) {
  const rad = (deg * Math.PI) / 180;
  return { x: CX + Math.cos(rad) * radius, y: CY + Math.sin(rad) * radius };
}

type ScopeState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; papers: PaperListItem[]; total: number };

export default function RadarScope() {
  const [state, setState] = useState<ScopeState>({ status: "loading" });
  const [activeId, setActiveId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchPapers({ page_size: 12 })
      .then((res) => {
        if (!cancelled) {
          setState({ status: "ready", papers: res.items, total: res.total });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setState({ status: "error" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const papers = state.status === "ready" ? state.papers : [];
  const active = activeId === null ? undefined : papers.find((p) => p.id === activeId);
  const idleMessage =
    state.status === "loading"
      ? "Acquiring contacts"
      : state.status === "error"
        ? "Scope offline — results unavailable"
        : papers.length === 0
          ? "No detections yet"
          : "Hover a detection to identify";

  const trail = polar(-28, R_OUT);
  const lead = polar(0, R_OUT);

  return (
    <section aria-label="Radar scope of latest papers" className="relative overflow-hidden px-4 pb-4 pt-4 md:px-5">
      <header className="flex items-center justify-between">
        <span className="font-mono text-xs tracking-[0.18em] text-haze">SCOPE</span>
        {state.status === "loading" && (
          <span className="font-mono text-xs text-haze">ACQUIRING…</span>
        )}
        {state.status === "error" && (
          <span className="font-mono text-xs text-signal">SCOPE OFFLINE</span>
        )}
        {state.status === "ready" && (
          <span className="font-mono text-xs tabular-nums text-haze">
            {state.total} PAPERS INDEXED
          </span>
        )}
      </header>

      <div className="mt-1 flex flex-wrap items-center gap-x-6 gap-y-2">
        <div className="relative min-w-0 max-w-[560px] flex-1 basis-[320px]">
          <svg
            viewBox="0 0 640 400"
            className="block h-auto w-full"
            aria-hidden="true"
            focusable="false"
          >
            <circle cx={CX} cy={CY} r={R_OUT} className="fill-well/40" />
            {[60, 120, 180].map((r) => (
              <circle key={r} cx={CX} cy={CY} r={r} fill="none" stroke="#3E6E96" strokeWidth={1} />
            ))}
            <circle cx={CX} cy={CY} r={R_OUT} fill="none" stroke="#9FC4DE" strokeWidth={1.5} />
            <line
              x1={CX - R_OUT}
              x2={CX + R_OUT}
              y1={CY}
              y2={CY}
              stroke="#3E6E96"
              strokeWidth={1}
              opacity={0.6}
            />
            <line
              x1={CX}
              x2={CX}
              y1={CY - R_OUT}
              y2={CY + R_OUT}
              stroke="#3E6E96"
              strokeWidth={1}
              opacity={0.6}
            />
            {SPOKE_ANGLES.map((deg) => {
              const tip = polar(deg, R_OUT);
              return (
                <line
                  key={deg}
                  x1={CX}
                  y1={CY}
                  x2={tip.x}
                  y2={tip.y}
                  stroke="#3E6E96"
                  opacity={0.25}
                />
              );
            })}
            {TICK_ANGLES.map((deg) => {
              const outer = polar(deg, R_OUT);
              const inner = polar(deg, R_OUT - (deg % 90 === 0 ? 10 : 6));
              return (
                <line
                  key={deg}
                  x1={inner.x}
                  y1={inner.y}
                  x2={outer.x}
                  y2={outer.y}
                  stroke="#9FC4DE"
                  opacity={0.5}
                />
              );
            })}
            {/* transform-box: view-box keeps the CSS rotation origin in viewBox units */}
            <g
              className="radar-sweep"
              style={{ transformOrigin: "320px 200px", transformBox: "view-box" }}
            >
              <path
                d={`M ${CX} ${CY} L ${trail.x.toFixed(1)} ${trail.y.toFixed(1)} A ${R_OUT} ${R_OUT} 0 0 1 ${lead.x.toFixed(1)} ${lead.y.toFixed(1)} Z`}
                fill="#FFB03C"
                opacity={0.07}
              />
              <line
                x1={CX}
                y1={CY}
                x2={lead.x}
                y2={lead.y}
                stroke="#FFB03C"
                strokeWidth={1.5}
                opacity={0.9}
              />
            </g>
          </svg>

          {papers.slice(0, 12).map((paper, idx) => {
            // Golden-angle spread by id; ring depth cycles by index for even coverage.
            const angle = (paper.id * 137.508) % 360;
            const rf = 0.3 + ((idx * 0.16) % 0.62);
            const rad = (angle * Math.PI) / 180;
            const x = CX + Math.cos(rad) * R_OUT * rf;
            const y = CY + Math.sin(rad) * R_OUT * rf;
            const isActive = activeId === paper.id;
            return (
              <a
                key={paper.id}
                href={`/papers/${paper.id}`}
                aria-label={`View paper: ${paper.title}`}
                className="group absolute flex items-center justify-center p-[18px]"
                style={{
                  left: `${(x / 640) * 100}%`,
                  top: `${(y / 400) * 100}%`,
                  transform: "translate(-50%, -50%)",
                }}
                onMouseEnter={() => setActiveId(paper.id)}
                onMouseLeave={() => setActiveId(null)}
                onFocus={() => setActiveId(paper.id)}
                onBlur={() => setActiveId(null)}
              >
                <span
                  className={`pointer-events-none absolute inset-0 scale-150 rounded-full border border-signal transition duration-200 ${
                    isActive ? "scale-100 opacity-100" : "opacity-0"
                  }`}
                />
                <span
                  className={`h-2 w-2 rounded-full transition duration-200 ${
                    isActive
                      ? "scale-125 bg-signal"
                      : "bg-linebright group-hover:scale-125 group-hover:bg-signal"
                  }`}
                />
              </a>
            );
          })}
        </div>

        {/* Readout column: what the scope is looking at, plus the latest contacts. */}
        <div className="w-60 shrink-0 pb-2 md:w-64">
          <div className="border border-line bg-well/90 px-3 py-2">
            {active ? (
              <>
                <p className="font-mono text-[11px] tracking-[0.18em] text-signal">CONTACT</p>
                <p className="mt-0.5 line-clamp-2 text-[13px] font-medium leading-snug text-ice">
                  {active.title}
                </p>
                <p className="mt-0.5 font-mono text-[11px] tabular-nums text-haze">
                  {active.publication_year} / {active.cited_by_count} CITATIONS
                </p>
              </>
            ) : (
              <>
                <p className="font-mono text-[11px] tracking-[0.18em] text-haze">CONTACT</p>
                <p className="mt-0.5 font-mono text-[11px] text-haze">{idleMessage}</p>
              </>
            )}
          </div>

          <p className="mt-4 font-mono text-[11px] tracking-[0.18em] text-haze">
            LATEST CONTACTS
          </p>
          <ul className="mt-1.5 border-t border-line/60">
            {papers.slice(0, 3).map((paper) => (
              <li key={paper.id} className="border-b border-line/60">
                <a
                  href={`/papers/${paper.id}`}
                  className="block px-0.5 py-2 text-[12px] leading-snug text-haze underline-offset-4 transition-colors hover:text-signal hover:underline"
                  onMouseEnter={() => setActiveId(paper.id)}
                  onMouseLeave={() => setActiveId(null)}
                  onFocus={() => setActiveId(paper.id)}
                  onBlur={() => setActiveId(null)}
                >
                  <span className="line-clamp-2">{paper.title}</span>
                </a>
              </li>
            ))}
            {state.status === "loading" && (
              <li className="py-2">
                <div className="shimmer h-4 w-full" />
              </li>
            )}
            {state.status === "error" && (
              <li className="py-2 font-mono text-[11px] text-haze">
                Contacts unavailable.
              </li>
            )}
          </ul>
        </div>
      </div>
    </section>
  );
}
