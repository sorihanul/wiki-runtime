# retrieval

`./retrieval` is the retrieval layer of this package.
Its job is to reduce read cost by narrowing the candidate set before full note reading.

Default layout:

- `hot.sqlite`
  - built from `./wiki_lite/WIKI`
- `cold.sqlite`
  - built from `./wiki`

Default query order:

1. `query-dual`
2. check hot results for recency
3. check cold results for canon stability

The point is simple: do not reread the whole workspace for every question.
