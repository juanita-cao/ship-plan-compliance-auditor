// Surveyor sea lion: same body/face as the maritime-ops-inbox mascot, with surveyor gear.
// Pure SVG + CSS animation; the chirp is synthesised with Web Audio (no asset files).
import { useRef, useState } from "react";
import { moodOf, type Mood } from "../state/mascot";

const MOVES = ["jump", "spin", "wiggle", "flip", "sidestep", "shake", "headbob", "slip"] as const;
const WORDS = ["Inspecting…", "All clear!", "Eee-eee!", "Safety first!", "Checked ✓", "Fish?"];
const LABEL: Record<Mood, string> = { tired: "Review queue is full", calm: "All calm", eating: "Snack time" };

const BLUE='#5AA8D6',DARK='#3F8DBB',NAVY='#1F3A68',BELLY='#D8EEF8',INK='#14202B';
const OR='#F28C28',DOR='#C9710F',REF='#E9EEF2',HAT='#FFC72C',DHAT='#E0A100',BRIM='#F2B705';

const CSS = `
.mm-dolphin{animation:mm-bob 3s ease-in-out infinite;transform-origin:60px 112px;transform-box:view-box}
.mm-calm .mm-eyes{animation:mm-blink 3s ease-in-out infinite;transform-origin:49px 48px;transform-box:view-box}
.mm-tired .mm-dolphin{animation:mm-sag 4s ease-in-out infinite}
.mm-eating .mm-jaw{animation:mm-chew .5s ease-in-out infinite;transform-origin:60px 72px;transform-box:view-box}
.mm-fish{animation:mm-nibble 1s ease-in-out infinite}
.mm-smoke{animation:mm-smoke 2s ease-out infinite;opacity:0;transform-box:fill-box;transform-origin:center}
.mm-smoke.s2{animation-delay:.66s}.mm-smoke.s3{animation-delay:1.32s}
.mm-calm .mm-pen{animation:mm-write 1.5s ease-in-out infinite;transform-box:view-box;transform-origin:25px 96px}
.mm-move-jump .mm-dolphin{animation:mm-jump .9s ease-out}
.mm-move-spin .mm-dolphin{animation:mm-spin .9s ease-in-out}
.mm-move-wiggle .mm-dolphin{animation:mm-wiggle .9s ease-in-out}
.mm-move-flip .mm-dolphin{animation:mm-flip .9s ease-in-out}
.mm-move-sidestep .mm-dolphin{animation:mm-sidestep 1.1s ease-in-out}
.mm-move-shake .mm-dolphin{animation:mm-shake 1.1s linear}
.mm-move-headbob .mm-head{animation:mm-headbob 1.2s ease-in-out}
.mm-move-slip .mm-dolphin{animation:mm-slip 1.1s cubic-bezier(.3,.7,.4,1)}
.mm-move-slip .mm-head{animation:mm-wobble 1.1s ease-in-out}
.mm-head{transform-box:view-box;transform-origin:60px 76px}
.mm-drops{opacity:0}
.mm-move-shake .mm-drops{animation:mm-drops 1.1s ease-out}
.mm-bubble{animation:mm-pop 1.4s ease-out forwards}
@keyframes mm-blink{0%,76%,86%,100%{transform:scaleY(1)}81%{transform:scaleY(.08)}}
@keyframes mm-bob{0%,100%{transform:translateY(0) rotate(-2deg)}50%{transform:translateY(-4px) rotate(2deg)}}
@keyframes mm-sag{0%,100%{transform:translateY(2px) rotate(-3deg)}50%{transform:translateY(4px) rotate(3deg)}}
@keyframes mm-chew{0%,100%{transform:scaleY(1)}50%{transform:scaleY(.3)}}
@keyframes mm-nibble{0%,100%{transform:translate(48px,74px)}50%{transform:translate(48px,72px)}}
@keyframes mm-write{0%,100%{transform:rotate(0)}25%{transform:rotate(-14deg)}50%{transform:rotate(4deg)}75%{transform:rotate(-10deg)}}
@keyframes mm-smoke{0%{opacity:0;transform:translate(0,14px) scale(.5)}25%{opacity:.85}100%{opacity:0;transform:translate(4px,-10px) scale(1.25)}}
@keyframes mm-jump{0%{transform:translateY(0)}40%{transform:translateY(-26px) rotate(-18deg)}70%{transform:translateY(-8px) rotate(10deg)}100%{transform:translateY(0)}}
@keyframes mm-spin{0%{transform:rotate(0)}100%{transform:rotate(360deg)}}
@keyframes mm-wiggle{0%,100%{transform:rotate(0)}20%{transform:rotate(-14deg)}40%{transform:rotate(12deg)}60%{transform:rotate(-10deg)}80%{transform:rotate(8deg)}}
@keyframes mm-flip{0%{transform:scaleX(1)}50%{transform:scaleX(-1) translateY(-10px)}100%{transform:scaleX(1)}}
@keyframes mm-sidestep{0%,100%{transform:translateX(0) rotate(0)}18%{transform:translateX(-14px) rotate(-10deg)}32%{transform:translateX(-14px) rotate(-4deg)}50%{transform:translateX(0) rotate(0)}68%{transform:translateX(14px) rotate(10deg)}82%{transform:translateX(14px) rotate(4deg)}}
@keyframes mm-shake{0%{transform:scale(1,1)}10%{transform:scale(1.08,.9)}15%{transform:rotate(-7deg) translateX(-2px)}22%{transform:rotate(7deg) translateX(2px)}29%{transform:rotate(-7deg) translateX(-2px)}36%{transform:rotate(7deg) translateX(2px)}43%{transform:rotate(-6deg) translateX(-2px)}50%{transform:rotate(6deg) translateX(2px)}57%{transform:rotate(-5deg)}64%{transform:rotate(5deg)}71%{transform:rotate(-3deg)}78%{transform:rotate(3deg)}90%,100%{transform:rotate(0) scale(1,1)}}
@keyframes mm-headbob{0%,100%{transform:rotate(0)}15%{transform:rotate(-16deg)}35%{transform:rotate(14deg)}55%{transform:rotate(-12deg)}75%{transform:rotate(10deg)}90%{transform:rotate(-3deg)}}
@keyframes mm-slip{0%{transform:translateX(0) rotate(0)}12%{transform:translateX(-18px) rotate(16deg)}22%{transform:translateX(-20px) rotate(20deg) translateY(2px)}34%{transform:translateX(3px) rotate(-8deg)}46%{transform:translateX(-2px) rotate(5deg)}58%{transform:translateX(1px) rotate(-3deg)}72%{transform:rotate(1.5deg)}100%{transform:translateX(0) rotate(0)}}
@keyframes mm-wobble{0%,100%{transform:rotate(0)}10%{transform:rotate(-20deg)}22%{transform:rotate(18deg)}34%{transform:rotate(-16deg)}46%{transform:rotate(12deg)}58%{transform:rotate(-8deg)}72%{transform:rotate(5deg)}86%{transform:rotate(-2deg)}}
@keyframes mm-drops{0%{opacity:0;transform:scale(.4)}20%{opacity:1}100%{opacity:0;transform:scale(1.5)}}
@keyframes mm-pop{0%{opacity:0;transform:translateY(4px) scale(.8)}15%{opacity:1;transform:translateY(0) scale(1)}80%{opacity:1}100%{opacity:0;transform:translateY(-6px)}}
@media (prefers-reduced-motion: reduce){.mm-root *{animation:none !important}}
`;

function clipboard(){return `
 <g transform="translate(88 78) rotate(-8)">
  <rect x="-2" y="0" width="17" height="23" rx="2" fill="#F5E6CC" stroke="#C9A66B" stroke-width="1"/>
  <rect x="3" y="-3" width="7" height="5" rx="1.3" fill="#9A7A45"/>
  <path d="M1.5 8h11M1.5 12h11M1.5 16h8" stroke="#A8A8A8" stroke-width=".9" stroke-linecap="round"/>
  <path d="M2 8.4l1.2 1.2 2.4-2.6" fill="none" stroke="#2E9E4F" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"/>
 </g>`;}

function mascotSVG(mood: Mood): string {
 const smoke = mood==='tired' ? `<g fill="#8E9BA8">
  <g class="mm-smoke"><circle cx="56" cy="6" r="6"/><circle cx="63" cy="3" r="7"/><circle cx="70" cy="7" r="5"/></g>
  <g class="mm-smoke s2"><circle cx="48" cy="2" r="5"/><circle cx="54" cy="-2" r="6"/><circle cx="60" cy="2" r="4.5"/></g>
  <g class="mm-smoke s3"><circle cx="66" cy="0" r="5"/><circle cx="72" cy="-4" r="6"/><circle cx="78" cy="0" r="4.5"/></g></g>` : '';
 const sleeve = (d: string) =>`<path d="${d}" fill="${OR}" stroke="${DOR}" stroke-width=".6"/>`;
 let arms='';
 if(mood==='eating'){
  arms=`${sleeve('M40 84 q-6 -10 6 -16 q4 4 2 10 z')}${sleeve('M80 84 q6 -10 -6 -16 q-4 4 -2 10 z')}
   <ellipse cx="46.5" cy="68.5" rx="3.2" ry="3" fill="${DARK}"/><ellipse cx="73.5" cy="68.5" rx="3.2" ry="3" fill="${DARK}"/>`;
 } else if(mood==='tired'){
  arms=`${sleeve('M40 82 q-8 10 -6 24 q6 -4 9 -16 z')}${sleeve('M80 82 q8 10 6 24 q-6 -4 -9 -16 z')}
   <ellipse cx="36" cy="107" rx="3.4" ry="3.2" fill="${DARK}"/>
   <g transform="translate(79 91) rotate(8)"><rect x="0" y="0" width="14" height="19" rx="2" fill="#F5E6CC" stroke="#C9A66B"/><rect x="3.5" y="-2.5" width="7" height="4.5" rx="1.2" fill="#9A7A45"/><path d="M2 7h10M2 11h10M2 15h6" stroke="#A8A8A8" stroke-width=".8"/></g>
   <ellipse cx="85" cy="95" rx="3.2" ry="3" fill="${DARK}"/>`;
 } else {
  arms=`${sleeve('M40 82 q-14 4 -16 14 q10 0 18 -7 z')}${clipboard()}
   <ellipse cx="25" cy="96" rx="3.6" ry="3.2" fill="${DARK}"/>
   ${sleeve('M80 82 q10 -1 12 9 q-8 2 -14 -4 z')}
   <ellipse cx="91.5" cy="91" rx="3.4" ry="3" fill="${DARK}"/>
   <g class="mm-pen"><path d="M25 96 l-7 -12" stroke="#1F3A68" stroke-width="1.8" stroke-linecap="round"/><path d="M18 84 l-1.3 -2.3" stroke="#C8402F" stroke-width="1.8" stroke-linecap="round"/></g>`;
 }
 const eyes = mood==='tired'
  ? `<g fill="none" stroke="${INK}" stroke-width="2.2" stroke-linecap="round"><path d="M44 50 q5 4 10 0"/><path d="M66 50 q5 4 10 0"/></g>`
  : mood==='eating'
  ? `<g fill="none" stroke="${INK}" stroke-width="2.2" stroke-linecap="round"><path d="M44 50 q5 -5 10 0"/><path d="M66 50 q5 -5 10 0"/></g>`
  : `<g><g class="mm-eyes"><ellipse cx="49" cy="48" rx="4.2" ry="5.2" fill="${INK}"/><circle cx="50.5" cy="46" r="1.5" fill="#fff"/></g><ellipse cx="71" cy="48" rx="4.2" ry="5.2" fill="${INK}"/><circle cx="72.5" cy="46" r="1.5" fill="#fff"/></g>`;
 const mouth = mood==='tired'
  ? `<path d="M55.5 72.5 q4.5 -3 9 0" fill="none" stroke="${INK}" stroke-width="1.8" stroke-linecap="round"/>`
  : mood==='eating' ? `<ellipse class="mm-jaw" cx="60" cy="72" rx="3.6" ry="2.8" fill="#7A3B4A"/>`
  : `<path d="M55 70.5 q5 4.5 10 0" fill="#E0707A" stroke="${INK}" stroke-width="1.6" stroke-linecap="round"/>`;
 const fish = mood==='eating' ? `<g class="mm-fish" transform="translate(48 74)"><path d="M0 6 q10 -9 20 0 q-10 9 -20 0 z" fill="#F2A541"/><path d="M20 6 l6 -5 v10 z" fill="#F2A541"/><circle cx="5" cy="5" r="1.2" fill="${INK}"/></g>` : '';
 return `<svg width="112" height="120" viewBox="0 -16 120 136" aria-hidden="true">
 ${smoke}
 <g class="mm-drops" fill="#8FC3E6" style="transform-box:view-box;transform-origin:60px 70px"><circle cx="24" cy="54" r="2.4"/><circle cx="96" cy="50" r="2.4"/><circle cx="20" cy="84" r="2"/><circle cx="100" cy="82" r="2"/><circle cx="34" cy="30" r="1.8"/><circle cx="88" cy="28" r="1.8"/></g>
 <g class="mm-dolphin">
  <!-- coverall legs + boots -->
  <path d="M42 98 h36 v12 h-15 v-6 h-6 v6 h-15 z" fill="${OR}" stroke="${DOR}" stroke-width=".6"/>
  <rect x="42" y="104.6" width="15" height="2.4" fill="${REF}"/><rect x="63" y="104.6" width="15" height="2.4" fill="${REF}"/>
  <path d="M40 111 q9 -3 17 0 v4 q-8 3 -17 0 z" fill="${INK}"/><path d="M63 111 q9 -3 17 0 v4 q-8 3 -17 0 z" fill="${INK}"/>
  <!-- coverall torso -->
  <defs><clipPath id="mm-suit"><ellipse cx="60" cy="88" rx="22" ry="17"/></clipPath></defs>
  <g clip-path="url(#mm-suit)">
   <rect x="36" y="70" width="48" height="36" fill="${OR}"/>
   <rect x="36" y="85" width="48" height="3.2" fill="${REF}"/><rect x="36" y="93" width="48" height="3.2" fill="${REF}"/>
   <rect x="36" y="85" width="48" height=".6" fill="#B9C3CC"/><rect x="36" y="93" width="48" height=".6" fill="#B9C3CC"/>
   <path d="M60 76 V106" stroke="${DOR}" stroke-width="1.2"/>
   <rect x="67" y="77" width="7" height="6" rx="1" fill="none" stroke="${DOR}" stroke-width=".8"/>
  </g>
  <path d="M47 73 l13 12 l13 -12 z" fill="${DOR}"/>
  <path d="M53 76 l7 6 l7 -6" fill="none" stroke="#FFD9A8" stroke-width="1"/>
  ${arms}
  <g class="mm-head">
   <circle cx="60" cy="50" r="28" fill="${BLUE}"/>
   <ellipse cx="60" cy="60" rx="19" ry="13" fill="${BELLY}"/>
   <!-- hard hat with PVCB badge -->
   <path d="M35 35 C35 17 46 9 60 9 C74 9 85 17 85 35 Z" fill="${HAT}" stroke="${DHAT}" stroke-width=".8"/>
   <path d="M56.5 9.3 h7 v25.7 h-7 z" fill="${DHAT}" opacity=".85"/>
   <path d="M41 24 q5 -9 14 -11" fill="none" stroke="#FFF3B8" stroke-width="1.6" stroke-linecap="round" opacity=".7"/>
   <ellipse cx="60" cy="35.5" rx="29" ry="5" fill="${BRIM}" stroke="${DHAT}" stroke-width=".8"/>
   <circle cx="60" cy="26" r="4.4" fill="${NAVY}"/><circle cx="60" cy="26" r="1.7" fill="#E7B84A"/>
   <g fill="${DARK}" opacity=".55"><circle cx="37" cy="47" r="2.2"/><circle cx="34" cy="55" r="1.6"/><circle cx="83" cy="47" r="2.2"/><circle cx="86" cy="55" r="1.6"/></g>
   <ellipse cx="54.5" cy="64" rx="6.8" ry="5.2" fill="#EEF8FD" stroke="#B9DCEE" stroke-width=".8"/>
   <ellipse cx="65.5" cy="64" rx="6.8" ry="5.2" fill="#EEF8FD" stroke="#B9DCEE" stroke-width=".8"/>
   <g fill="${INK}" opacity=".45"><circle cx="52" cy="63" r=".7"/><circle cx="55" cy="65.5" r=".7"/><circle cx="51.5" cy="66.5" r=".7"/><circle cx="68" cy="63" r=".7"/><circle cx="65" cy="65.5" r=".7"/><circle cx="68.5" cy="66.5" r=".7"/></g>
   <g stroke="${INK}" stroke-width=".8" stroke-linecap="round" opacity=".6"><path d="M48 62 L37 59 M48 64.5 L36 64.5 M48.5 67 L37.5 70"/><path d="M72 62 L83 59 M72 64.5 L84 64.5 M71.5 67 L82.5 70"/></g>
   <path d="M56.8 59.4 q3.2 -1.6 6.4 0 q-1 3.2 -3.2 3.8 q-2.2 -.6 -3.2 -3.8 z" fill="${INK}"/>
   ${eyes}
   ${mood!=='tired'?`<g fill="#F4A7B9" opacity=".8"><ellipse cx="41" cy="58" rx="4" ry="2.4"/><ellipse cx="79" cy="58" rx="4" ry="2.4"/></g>`:''}
   ${mouth}
   ${mood==='tired'?`<path d="M88 40 q4 6 0 9 q-4 -3 0 -9 z" fill="#8FC3E6"/>`:''}
  </g>
  ${fish}
 </g></svg>`;}

function chirp() {try{const A = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;const c=new A();const now=c.currentTime;const n=1+Math.floor(Math.random()*3);
 for(let i=0;i<n;i++){const o=c.createOscillator(),g=c.createGain(),s=now+i*.13,b=900+Math.random()*700;o.type='sine';
 o.frequency.setValueAtTime(b,s);o.frequency.exponentialRampToValueAtTime(b*(1.6+Math.random()),s+.08);o.frequency.exponentialRampToValueAtTime(b*.9,s+.12);
 g.gain.setValueAtTime(.0001,s);g.gain.exponentialRampToValueAtTime(.12,s+.02);g.gain.exponentialRampToValueAtTime(.0001,s+.12);o.connect(g).connect(c.destination);o.start(s);o.stop(s+.13);}
 setTimeout(()=>c.close(),800);}catch(e){}}


export function SeaLionMascot({ pending }: { pending: number }) {
  const mood = moodOf(pending);
  const [move, setMove] = useState<string | null>(null);
  const [word, setWord] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);

  const play = () => {
    const m = MOVES[Math.floor(Math.random() * MOVES.length)];
    setMove(null);
    requestAnimationFrame(() => setMove(m));
    setWord(WORDS[Math.floor(Math.random() * WORDS.length)]);
    chirp();
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => { setMove(null); setWord(null); }, 1400);
  };

  return (
    <div
      className={`mm-root mm-${mood} ${move ? `mm-move-${move}` : ""}`}
      style={{ position: "relative", display: "flex", flexDirection: "column", alignItems: "center", padding: "4px 0 8px" }}
    >
      <style>{CSS}</style>
      {word && (
        <span className="mm-bubble" style={{ position: "absolute", top: -6, right: 18, fontSize: 11, fontWeight: 600, background: "#fff", color: "#14202B", border: "1px solid #D9E0E9", borderRadius: 10, padding: "1px 8px", whiteSpace: "nowrap" }}>
          {word}
        </span>
      )}
      <button
        type="button" onClick={play}
        aria-label={`Sea lion: ${LABEL[mood]}, ${pending} pending reviews. Click to play`}
        style={{ border: 0, background: "transparent", padding: 0, cursor: "pointer", lineHeight: 0 }}
        dangerouslySetInnerHTML={{ __html: mascotSVG(mood) }}
      />
    </div>
  );
}
