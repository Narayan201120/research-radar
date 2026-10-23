"use client";

import { useEffect, useRef, useState } from "react";

export interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps {
  id: string;
  label: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  /** Wrapper width, e.g. "w-24". */
  className?: string;
  /** Mono tabular value text, for year-like readouts. */
  mono?: boolean;
}

// Custom listbox dropdown. The native <select> popup is OS-drawn and cannot
// match the console, so this renders the trigger and popup in-design, with
// the standard listbox keyboard path (arrows, Enter, Escape) wired.
export default function Select({
  id,
  label,
  value,
  options,
  onChange,
  className = "",
  mono = false,
}: SelectProps) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const selected = options.find((o) => o.value === value) ?? options[0];
  const labelCls = "block font-mono text-[11px] tracking-[0.18em] text-haze";

  useEffect(() => {
    if (!open) return;
    listRef.current?.focus();
    const onPointerDown = (e: PointerEvent) => {
      if (!wrapperRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  const openList = () => {
    const idx = Math.max(0, options.findIndex((o) => o.value === value));
    setActive(idx);
    setOpen(true);
  };

  const pick = (v: string) => {
    onChange(v);
    setOpen(false);
  };

  const handleListKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const delta = e.key === "ArrowDown" ? 1 : -1;
      const next = (active + delta + options.length) % options.length;
      setActive(next);
      listRef.current
        ?.querySelector(`#${id}-option-${next}`)
        ?.scrollIntoView({ block: "nearest" });
    } else if (e.key === "Home") {
      e.preventDefault();
      setActive(0);
    } else if (e.key === "End") {
      e.preventDefault();
      setActive(options.length - 1);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      pick(options[active].value);
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
    } else if (e.key === "Tab") {
      setOpen(false);
    }
  };

  return (
    <div className={className} ref={wrapperRef}>
      <span id={`${id}-label`} className={labelCls}>
        {label}
      </span>
      <div className="relative mt-1.5">
        <button
          type="button"
          id={`${id}-button`}
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-labelledby={`${id}-label ${id}-button`}
          onClick={() => (open ? setOpen(false) : openList())}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown" || e.key === "ArrowUp") {
              e.preventDefault();
              openList();
            }
          }}
          className="flex min-h-[38px] w-full items-center justify-between gap-2 border border-line bg-well px-2.5 py-2 text-sm leading-[1.55] text-ice transition-colors hover:border-linebright"
        >
          <span className={`min-w-0 truncate ${mono ? "font-mono text-[13px] tabular-nums" : ""}`}>
            {selected?.label ?? ""}
          </span>
          <svg
            aria-hidden="true"
            viewBox="0 0 12 12"
            className={`h-2.5 w-2.5 shrink-0 transition-transform duration-150 ${
              open ? "rotate-180 text-signal" : "text-haze"
            }`}
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path d="M2 4l4 4 4-4" />
          </svg>
        </button>

        {open && (
          <ul
            role="listbox"
            id={`${id}-listbox`}
            aria-labelledby={`${id}-label`}
            aria-activedescendant={`${id}-option-${active}`}
            tabIndex={-1}
            ref={listRef}
            onKeyDown={handleListKey}
            className="absolute left-0 right-0 top-[calc(100%+4px)] z-20 max-h-64 overflow-y-auto border border-line bg-panel"
          >
            {options.map((o, i) => {
              const isSelected = o.value === value;
              return (
                <li
                  key={o.value}
                  id={`${id}-option-${i}`}
                  role="option"
                  aria-selected={isSelected}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => pick(o.value)}
                  className={`flex min-h-[34px] cursor-pointer items-center gap-2 px-2.5 py-1.5 text-sm leading-[1.55] ${
                    i === active ? "bg-well text-ice" : "text-haze"
                  }`}
                >
                  <span
                    aria-hidden="true"
                    className={`h-3.5 w-0.5 shrink-0 ${
                      isSelected ? "bg-signal" : "bg-transparent"
                    }`}
                  />
                  <span
                    className={`min-w-0 truncate ${
                      isSelected ? "text-ice" : ""
                    } ${mono ? "font-mono text-[13px] tabular-nums" : ""}`}
                  >
                    {o.label}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
