# Accessibility checklist — offline release

**Checked:** 2026-09-03  
**Scope:** critical program-selection and model-evaluation flow

| Check | Evidence | Status |
|---|---|---|
| Keyboard operation | The critical flow uses native Streamlit selectbox, tab, expander, and scroll interactions; no pointer-only custom control is introduced | verified |
| Visible focus | A global `:focus-visible` rule provides a 3 px `#005fcc` outline with a 3 px offset | verified |
| Non-color status | Historical interval state, missingness, projection eligibility, model selection, and band suppression all have explicit text labels | verified |
| WCAG AA text/control contrast | Custom marks on white are `#315f7d` (6.85:1), `#7a5195` (6.11:1), and `#59636e` (6.11:1); the focus outline is `#005fcc` (5.98:1) | verified |
| Chart interpretation | Charts include titles, labeled axes, hover values, source captions, a labeled reference meaning in the caption, and gap semantics | verified |
| Missing values | Missing ratios render as “Not reported” or an explicit unavailable state, never as zero | verified |
| Interval distinction | Historical vertical marks are explicitly labeled SRTR 95% credible intervals; no empirical forecast band is shown in this release | verified |
| Automated critical path | Streamlit AppTest exercises program selection, history, donor strata, projection state, model status, and provenance from the tracked bundle without network access | verified |

The application relies on Streamlit’s native semantic controls. This bounded review does not claim
a complete WCAG conformance audit across every browser, operating system, or assistive technology.

