# Setting up your COOs

The release ships with one role already in place: the **Production VP**. Which COOs you run is your call, not ours.
This guide helps you decide. The Chief of Staff walks you through the same steps as dialogs on its first run, and again
any time you tell it "add a COO".

## What a COO is

A COO is one long-running Claude Code session that owns **one area** of your work end to end. It:
- keeps a charter (what it owns, what it may decide alone) and 3-5 goals;
- starts worker sessions on cheap models for the actual work and checks their results;
- writes one report line per pass that the Chief of Staff reads;
- sends questions up only when it truly needs you, always with a recommended answer;
- gets trained like an employee: its corrections become lessons, lessons become rules, and it is tested on what it knows.

A COO does not code or write itself. It coordinates.

## The shape

```
you
 └─ Chief of Staff
     ├─ Production VP  (standard)  ── product COOs: one per product or business line
     └─ other COOs (optional)      ── IT, admin, growth, personal: report straight to the Chief of Staff
```

- **Product COOs** report build and board status to the **Production VP**, which keeps quality and delivery consistent
  across products. Their questions for you still reach you through the Chief of Staff.
- **Other COOs** (anything that is not a product line) report directly to the Chief of Staff.
- With only one product, the VP has little to supervise. Keep it anyway: it costs nothing while idle and is ready when
  you add a second product.

## How to choose

Start from what you actually spend time on. Ask yourself:

1. **What do you sell or build?** Each product, app, client service or business line that has its own customers,
   repo or revenue is a **product COO**.
2. **What recurring work keeps you busy that is not a product?** Common choices:
   - **IT**: computers, accounts, networks, backups, security reviews.
   - **Admin / finance**: bills, invoices, taxes, contracts, paperwork.
   - **Growth / marketing**: content, outreach, social, campaigns. One shared growth COO is usually enough. Split it
     per product only when each product has its own sustained marketing.
   - **Personal**: health, family logistics, home, travel. Keep it separate so private work stays in its own lane.
3. **Is there enough work?** A COO earns its place when the area has work most weeks. Occasional tasks can go to the
   Chief of Staff directly, and it routes them.

Rules of thumb:
- **One COO per area, never two.** Two COOs on one product will step on each other.
- **Start small.** Two or three COOs you will really use beat eight that sit idle. You can add more any time.
- **Merge** two COOs when they keep handing work to each other or one is idle for a month.
- **Split** a COO when its report covers two unrelated things every week, or it keeps getting corrected for mixing them up.

## Examples

| You are | A good start |
|---|---|
| A solo founder with one SaaS app | `App` (product), `Admin`, `Growth` (other) |
| An agency with three client accounts | one product COO per client, `Admin` |
| A developer with two side projects and a day job | one product COO per project, `Personal` |
| A small company with two products and an office | one product COO per product, `IT`, `Admin`, `Growth` |

## Setting one up

The easy way is to tell the Chief of Staff **"add a COO"**. It asks you a few questions as dialogs and does the rest.
Done by hand, the steps are:

```bash
cos add-project "My App"                       # a product COO (reports to the Production VP)
cos add-project "IT" --reports-to cos          # a non-product COO (reports to the Chief of Staff)
```

1. Edit `<data folder>/Context/<Name>/COO_CHARTER.md`. Write what it owns, what winning looks like, what it may decide
   alone, and what must come to you.
2. Edit `GOALS.md` with 3-5 goals, each with a measure, a target and a status line.
3. Run `python3 ~/.claude/chief-of-staff/bin/coo_onboard.py <Name>`. This builds its five training files.
4. Tell the Chief of Staff: "start the <Name> COO". It starts a session titled `<Name> COO` that loops every 3 hours.

`cos list-coos` shows the Production VP and every COO, whom each reports to, and whether its training files exist.

## Changing your mind

- **Retire a COO:** ask the Chief of Staff to stop it, then remove its line from `projects:` in `~/.claude/cos-config.yaml`.
  Its files stay in the data folder.
- **Rename or merge:** ask the Chief of Staff. It writes the old COO's state file, starts the new one from it, and
  retires the old one, so you never have two COOs for one area.
