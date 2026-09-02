import { useEffect, useRef, useState } from "react";

/** One place to ask, so a change of heart is a one-line change. */
export function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true
  );
}

/**
 * True once the element has been on screen, and true forever after.
 *
 * Reveal-on-scroll that re-hides is a nuisance: a reader who scrolls back up a
 * page has already seen it, and animating it again is the page arguing with
 * them. So the observer disconnects on the first intersection.
 *
 * Where reduced motion is asked for, this returns true from the first render
 * and nothing ever animates - the content is never withheld pending an effect.
 */
export function useReveal<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [shown, setShown] = useState(() => prefersReducedMotion());
  // Armed only once this hook is running, so the CSS that hides a section
  // never applies unless something is guaranteed to show it again. Content
  // withheld pending JavaScript is content lost when JavaScript does not run.
  const [armed, setArmed] = useState(false);

  useEffect(() => setArmed(true), []);

  useEffect(() => {
    if (shown) return;
    const node = ref.current;
    // No IntersectionObserver (or no node) must not mean no content.
    if (!node || typeof IntersectionObserver === "undefined") {
      setShown(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setShown(true);
          observer.disconnect();
        }
      },
      // A little before the edge, so a section is already settled by the time
      // it is properly in view.
      { rootMargin: "0px 0px -12% 0px", threshold: 0.08 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [shown]);

  return { ref, shown, armed } as const;
}

/**
 * Counts up to `value` once `start` goes true.
 *
 * The rupee figures are the emotional content of this page, and a number that
 * lands rather than simply being there is the difference. Reduced motion gets
 * the final figure immediately - the information, never the performance.
 */
export function useCountUp(value: number, start: boolean, duration = 900): number {
  const [shown, setShown] = useState(() => (prefersReducedMotion() ? value : 0));

  useEffect(() => {
    if (!start || prefersReducedMotion()) {
      setShown(value);
      return;
    }

    let frame = 0;
    const began = performance.now();
    const tick = (now: number) => {
      const progress = Math.min(1, (now - began) / duration);
      // Ease out: fast at first, settling rather than stopping.
      const eased = 1 - Math.pow(1 - progress, 3);
      setShown(Math.round(value * eased));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, start, duration]);

  return shown;
}
