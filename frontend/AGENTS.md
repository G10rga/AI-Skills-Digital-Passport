<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

## Project rules
- Frontend only; all data access goes through `src/lib/api.ts` (mock, localStorage-backed) so a separate backend can replace it 1:1 — contract in `API_CONTRACT.md`.
- Data routes use `ssr: false` because the mock store lives in the browser.
