// (() => {
//   'use strict';

//   const $  = (sel, root = document) => root.querySelector(sel);
//   const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
//   const csrf = $('meta[name="csrf-token"]')?.content;
//   const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

//   /* ---------- Sidebar drawer (mobile hamburger) ---------- */
//   const sidebar  = $('#sidebar');
//   const backdrop = $('#sidebar-backdrop');

//   function setSidebar(open) {
//     if (!sidebar) return;
//     sidebar.dataset.open = String(open);
//     if (backdrop) backdrop.dataset.open = String(open);
//     $$('button[data-sidebar-toggle]').forEach(b => b.setAttribute('aria-expanded', String(open)));
//     document.body.style.overflow = open && !matchMedia('(min-width: 1024px)').matches ? 'hidden' : '';
//   }

//   /* ---------- Click handlers (delegated) ---------- */
//   document.addEventListener('click', async (e) => {
//     // sidebar open/close
//     if (e.target.closest('[data-sidebar-toggle]')) {
//       setSidebar(sidebar?.dataset.open !== 'true');
//       return;
//     }
//     if (sidebar?.dataset.open === 'true' && e.target.closest('#sidebar a')) setSidebar(false);

//     // back to top
//     if (e.target.closest('[data-back-top]')) {
//       window.scrollTo({ top: 0, behavior: reduceMotion ? 'auto' : 'smooth' });
//       return;
//     }

//     // dismiss flash message
//     const dismiss = e.target.closest('[data-dismiss]');
//     if (dismiss) { dismiss.closest('[data-flash]')?.remove(); return; }

//     // show/hide password
//     const toggle = e.target.closest('[data-toggle-password]');
//     if (toggle) {
//       const input = $(toggle.dataset.togglePassword);
//       if (!input) return;
//       const show = input.type === 'password';
//       input.type = show ? 'text' : 'password';
//       toggle.textContent = show ? 'Hide' : 'Show';
//       return;
//     }

//     // mark lesson complete without reloading the page
//     const complete = e.target.closest('[data-complete-url]');
//     if (complete) {
//       complete.disabled = true;
//       try {
//         const res = await fetch(complete.dataset.completeUrl, {
//           method: 'POST',
//           headers: { 'X-CSRFToken': csrf, 'Accept': 'application/json' },
//         });
//         if (!res.ok) throw new Error('Request failed');
//         const data = await res.json();          // { completed: true/false, percent: 0-100 }
//         complete.textContent = data.completed ? 'Completed. Undo' : 'Mark as complete';
//         complete.classList.toggle('btn-primary', !data.completed);
//         complete.classList.toggle('btn-outline', data.completed);
//         $$('[data-progress-bar]').forEach(b => { b.style.width = data.percent + '%'; });
//         $$('[data-progress-text]').forEach(t => { t.textContent = data.percent + '% complete'; });
//       } catch {
//         complete.textContent = 'Something went wrong. Try again';
//       } finally {
//         complete.disabled = false;
//       }
//     }
//   });

//   document.addEventListener('keydown', (e) => {
//     if (e.key === 'Escape' && sidebar?.dataset.open === 'true') setSidebar(false);
//   });

//   /* ---------- Auto-dismiss success/info flash messages ---------- */
//   $$('[data-flash]').forEach((el) => {
//     if (/bg-(green|blue)-50/.test(el.className)) setTimeout(() => el.remove(), 6000);
//   });

//   /* ---------- Scroll reveal ---------- */
//   function reveal(root = $('#app')) {
//     if (!root || reduceMotion || !('IntersectionObserver' in window)) return;

//     const candidates = $$('h1, h2, p, form, .card, article, details, [class*="aspect-"], section div.flex-wrap.gap-3', root)
//       .filter(el => !el.closest('[data-no-reveal]'));
//     // skip anything nested inside another animated element
//     const targets = candidates.filter(el => !candidates.some(o => o !== el && o.contains(el)));

//     const counts = new Map();                      // stagger siblings
//     targets.forEach((el) => {
//       const i = counts.get(el.parentElement) || 0;
//       counts.set(el.parentElement, i + 1);
//       el.classList.add('rv');
//       el.style.setProperty('--d', Math.min(i, 6) * 100 + 'ms');
//     });

//     const io = new IntersectionObserver((entries) => {
//       entries.forEach((entry) => {
//         if (!entry.isIntersecting) return;
//         const el = entry.target;
//         el.classList.add('in');
//         io.unobserve(el);
//         setTimeout(() => { el.classList.remove('rv', 'in'); el.style.removeProperty('--d'); }, 1500);
//       });
//     }, { threshold: 0.1, rootMargin: '0px 0px -5% 0px' });

//     targets.forEach(el => io.observe(el));
//   }

//   reveal();
// })();