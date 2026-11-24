# Roadmap

Status as of the last doc update. Tick items when done; remove ticked items after the next release.

## Release 0.3.0

- [x] Make the graph the default, with a nearest marker and the existing fold counts.
- [x] Filter full branch ref names and count aliases on the same tip as one place in the graph.
- [x] Share center, filter, limit, fold expansion and commit details across command and interactive views.
- [x] Print the final interactive view into normal terminal scrollback on exit.

## Release 0.4.0

- [x] Cache commit details and the graph layout so repeated toggles require no Git calls.
- [x] Add a bounded graph of real commits and edges with branch waypoints at the boundary.
- [x] Walk parent and child edges in interactive mode and choose a route at forks.
- [x] Render the same neighborhood directly with `--radius` and keep the final view in scrollback.

## Later

- [ ] Optional: answer the Stack Overflow question "How to find the nearest parent of a Git branch"
  with a link, once the package is public. **Confirm with the user first.**
