# Demo video

A [Remotion](https://www.remotion.dev/) project that replays one real incident
(`runs/20261123T204228Z_payment-down`) from its run files in `public/run/`. Every number and finding
on screen is read from those files; the screenshots in `public/shots/` were taken during that run.

```sh
npm install
npx remotion studio                                   # preview and scrub
npx remotion render Pagerless out/pagerless.mp4       # render, then copy to docs/media/
```
