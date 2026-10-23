// Blueprint corner ticks for the page frame. Purely structural decoration
// marking the drawing extents; hidden from assistive tech.
export default function CornerTicks() {
  const tick = "absolute h-3 w-3 border-linebright";
  return (
    <div aria-hidden="true">
      <span className={`${tick} left-0 top-0 border-l border-t`} />
      <span className={`${tick} right-0 top-0 border-r border-t`} />
      <span className={`${tick} bottom-0 left-0 border-b border-l`} />
      <span className={`${tick} bottom-0 right-0 border-b border-r`} />
    </div>
  );
}
