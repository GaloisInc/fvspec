#import "@preview/cetz:0.4.2"

#let read-jsonl(path) = {
  read("data/" + path) // Read the file as a string
    .split("\n")       // Split into individual lines
    .filter(line => line.trim() != "") // Remove empty lines
    .map(line => json(bytes(line)))  // Parse each line as JSON
}

#let config = toml("config.toml")

#let fvspec = read-jsonl(config.fvspec_file)

#let fvspec_n = fvspec.len()

#let pipeline-diagram() = {
  cetz.canvas(length: 1cm, {
    import cetz.draw: *

    // Style helpers
    let box-fill = rgb("#e8f0fa")
    let box-stroke = rgb("#4a7cb5") + 0.8pt
    let agent-fill = rgb("#dceefb")
    let agent-stroke = rgb("#2d6da3") + 0.8pt
    let eval-fill = rgb("#f5eadb")
    let eval-stroke = rgb("#b5874a") + 0.8pt
    let arrow-stroke = rgb("#333") + 0.7pt
    let loop-stroke = rgb("#888") + 0.7pt
    let lsp-fill = rgb("#f0f0f0")
    let lsp-stroke = rgb("#888") + 0.6pt

    let bw = 2.8   // box width
    let bh = 0.8   // box height
    let lsp-w = 2.4

    // ── Row 0: RealPBT input ──
    let y0 = 0
    rect((-bw/2, y0 - bh/2), (bw/2, y0 + bh/2),
      fill: box-fill, stroke: box-stroke, radius: 3pt)
    content((0, y0), text(size: 7pt, weight: "bold")[RealPBT Sample])

    // ── Row 1: Function Discovery ──
    let y1 = y0 - 1.3
    line((0, y0 - bh/2), (0, y1 + bh/2 + 0.05), stroke: arrow-stroke, mark: (end: ">", fill: rgb("#333")))
    rect((-bw/2, y1 - bh/2), (bw/2, y1 + bh/2),
      fill: rgb("#f0f0f0"), stroke: rgb("#888") + 0.6pt, radius: 3pt)
    content((0, y1 + 0.1), text(size: 6.5pt, weight: "bold")[Function Discovery])
    content((0, y1 - 0.17), text(size: 5.5pt)[tree-sitter extraction])

    // ── Row 2: Impl Agent ──
    let y2 = y1 - 1.3
    line((0, y1 - bh/2), (0, y2 + bh/2 + 0.05), stroke: arrow-stroke, mark: (end: ">", fill: rgb("#333")))
    content((0.15, (y1 - bh/2 + y2 + bh/2) / 2), anchor: "west", text(size: 5pt, fill: rgb("#666"))[FUT + deps])
    rect((-bw/2, y2 - bh/2), (bw/2, y2 + bh/2),
      fill: agent-fill, stroke: agent-stroke, radius: 3pt)
    content((0, y2 + 0.12), text(size: 6.5pt, weight: "bold")[Impl Agent])
    content((0, y2 - 0.18), text(size: 5.5pt)[computable, no `sorry`])

    // ── Row 3: Lean LSP for impl ──
    let y3 = y2 - 1.3
    rect((-lsp-w/2, y3 - bh/2), (lsp-w/2, y3 + bh/2),
      fill: lsp-fill, stroke: lsp-stroke, radius: 3pt)
    content((0, y3), text(size: 6.5pt)[Lean LSP typecheck])
    line((0, y2 - bh/2), (0, y3 + bh/2 + 0.05), stroke: arrow-stroke, mark: (end: ">", fill: rgb("#333")))

    // Impl repair loop (left side)
    let loop-x = -2.0
    line((-lsp-w/2, y3), (loop-x, y3), stroke: loop-stroke)
    line((loop-x, y3), (loop-x, y2), stroke: loop-stroke)
    line((loop-x, y2), (-bw/2 - 0.05, y2), stroke: loop-stroke, mark: (end: ">", fill: rgb("#888")))
    content((loop-x - 0.1, (y2 + y3) / 2), anchor: "east", text(size: 5pt, fill: rgb("#666"))[fix errors])

    // ── Branch point: success / fail ──
    let y-branch = y3 - 0.9
    line((0, y3 - bh/2), (0, y-branch), stroke: arrow-stroke)

    let x-succ = -1.5
    let x-fail = 1.5
    line((0, y-branch), (x-succ, y-branch), stroke: arrow-stroke)
    line((0, y-branch), (x-fail, y-branch), stroke: arrow-stroke)
    content((x-succ / 2, y-branch + 0.2), text(size: 5.5pt, fill: rgb("#2a7a2a"), weight: "bold")[success])
    content((x-fail / 2, y-branch + 0.2), text(size: 5.5pt, fill: rgb("#c44"), weight: "bold")[fail])

    // ── Signature extraction (on success path) ──
    let y-sig = y-branch - 0.8
    let sig-w = 2.2
    line((x-succ, y-branch), (x-succ, y-sig + 0.3 + 0.05), stroke: arrow-stroke, mark: (end: ">", fill: rgb("#333")))
    rect((x-succ - sig-w/2, y-sig - 0.3), (x-succ + sig-w/2, y-sig + 0.3),
      fill: lsp-fill, stroke: lsp-stroke, radius: 3pt)
    content((x-succ, y-sig + 0.05), text(size: 5.5pt, weight: "bold")[Extract Signatures])
    content((x-succ, y-sig - 0.17), text(size: 5pt)[from Impl.lean])

    // Fail path drops straight down to merge line
    let y-merge = y-sig - 0.7
    line((x-fail, y-branch), (x-fail, y-merge), stroke: arrow-stroke)
    content((x-fail + 0.15, (y-branch + y-merge) / 2), anchor: "west", text(size: 5pt, fill: rgb("#666"))[no impl])

    // ── Row 4: Spec + Units agents (parallel) ──
    let y4 = y-merge - 1.0
    let x-spec = -1.5
    let x-units = 1.5
    let abw = 2.5  // agent box width for this row

    // Success path: signatures -> spec agent
    line((x-succ, y-sig - 0.3), (x-spec, y4 + bh/2 + 0.05), stroke: arrow-stroke, mark: (end: ">", fill: rgb("#333")))
    content((x-spec + 0.15, (y-sig - 0.3 + y4 + bh/2) / 2 - 0.1), anchor: "west", text(size: 5pt, fill: rgb("#666"))[impl + sigs])

    // Fail path: straight down into both agents via horizontal merge
    line((x-fail, y-merge), (x-fail, y4 + bh/2 + 0.05), stroke: arrow-stroke, mark: (end: ">", fill: rgb("#333")))

    // "parallel" label
    content((0, y4), text(size: 5pt, fill: rgb("#999"), style: "italic")[parallel])

    // Spec agent box
    rect((x-spec - abw/2, y4 - bh/2), (x-spec + abw/2, y4 + bh/2),
      fill: agent-fill, stroke: agent-stroke, radius: 3pt)
    content((x-spec, y4 + 0.12), text(size: 6.5pt, weight: "bold")[Spec Agent])
    content((x-spec, y4 - 0.18), text(size: 5.5pt)[theorems with `sorry`])

    // Units agent box
    rect((x-units - abw/2, y4 - bh/2), (x-units + abw/2, y4 + bh/2),
      fill: agent-fill, stroke: agent-stroke, radius: 3pt)
    content((x-units, y4 + 0.12), text(size: 6.5pt, weight: "bold")[Units Agent])
    content((x-units, y4 - 0.18), text(size: 5.5pt)[LSpec test cases])

    // ── Row 5: LSP checks for both ──
    let y5 = y4 - 1.3
    // Spec LSP
    rect((x-spec - lsp-w/2, y5 - bh/2), (x-spec + lsp-w/2, y5 + bh/2),
      fill: lsp-fill, stroke: lsp-stroke, radius: 3pt)
    content((x-spec, y5), text(size: 6pt)[Lean LSP])
    line((x-spec, y4 - bh/2), (x-spec, y5 + bh/2 + 0.05), stroke: arrow-stroke, mark: (end: ">", fill: rgb("#333")))

    // Units LSP
    rect((x-units - lsp-w/2, y5 - bh/2), (x-units + lsp-w/2, y5 + bh/2),
      fill: lsp-fill, stroke: lsp-stroke, radius: 3pt)
    content((x-units, y5), text(size: 6pt)[Lean LSP])
    line((x-units, y4 - bh/2), (x-units, y5 + bh/2 + 0.05), stroke: arrow-stroke, mark: (end: ">", fill: rgb("#333")))

    // Spec repair loop (left)
    let loop-x2 = x-spec - 1.7
    line((x-spec - lsp-w/2, y5), (loop-x2, y5), stroke: loop-stroke)
    line((loop-x2, y5), (loop-x2, y4), stroke: loop-stroke)
    line((loop-x2, y4), (x-spec - abw/2 - 0.05, y4), stroke: loop-stroke, mark: (end: ">", fill: rgb("#888")))
    content((loop-x2 - 0.1, (y4 + y5) / 2), anchor: "east", text(size: 5pt, fill: rgb("#666"))[fix])

    // Units repair loop (right)
    let loop-x3 = x-units + 1.7
    line((x-units + lsp-w/2, y5), (loop-x3, y5), stroke: loop-stroke)
    line((loop-x3, y5), (loop-x3, y4), stroke: loop-stroke)
    line((loop-x3, y4), (x-units + abw/2 + 0.05, y4), stroke: loop-stroke, mark: (end: ">", fill: rgb("#888")))
    content((loop-x3 + 0.1, (y4 + y5) / 2), anchor: "west", text(size: 5pt, fill: rgb("#666"))[fix])

    // ── Row 6: lake build validation ──
    let y6 = y5 - 1.2
    line((x-spec, y5 - bh/2), (x-spec, y6 + 0.05), stroke: arrow-stroke)
    line((x-units, y5 - bh/2), (x-units, y6 + 0.05), stroke: arrow-stroke)
    line((x-spec, y6), (x-units, y6), stroke: arrow-stroke)
    let build-w = 2.0
    rect((-build-w/2, y6 - bh/2), (build-w/2, y6 + bh/2 - 0.1),
      fill: lsp-fill, stroke: lsp-stroke, radius: 3pt)
    content((0, y6 - 0.05), text(size: 6pt)[`lake build`])
    line((0, y6 + 0.05), (0, y6 + 0.05), stroke: arrow-stroke)

    // ── Row 7: Quality Assessment ──
    let y7 = y6 - 1.2
    line((0, y6 - bh/2 + 0.1), (0, y7 + bh/2 + 0.05), stroke: arrow-stroke, mark: (end: ">", fill: rgb("#333")))
    let eval-w = 3.6
    rect((-eval-w/2, y7 - bh/2), (eval-w/2, y7 + bh/2),
      fill: eval-fill, stroke: eval-stroke, radius: 3pt)
    content((0, y7 + 0.12), text(size: 6.5pt, weight: "bold")[Quality Assessment])
    content((0, y7 - 0.18), text(size: 5pt)[faithfulness (programmatic) + difficulty (LLM)])

    // ── Row 8: Output ──
    let y8 = y7 - 1.2
    line((0, y7 - bh/2), (0, y8 + bh/2 + 0.05), stroke: arrow-stroke, mark: (end: ">", fill: rgb("#333")))
    rect((-bw/2, y8 - bh/2), (bw/2, y8 + bh/2),
      fill: box-fill, stroke: box-stroke, radius: 3pt)
    content((0, y8), text(size: 7pt, weight: "bold")[Benchmark Problem])
  })
}

#let difficulty-histogram() = {
  // Extract grades and bucket into integer bins 1-10
  let grades = fvspec.map(s => s.difficulty_subjective_haiku)
  let bins = range(1, 11) // 1 through 10
  let counts = bins.map(b => {
    grades.filter(g => calc.floor(g) == b).len()
  })
  let max-count = calc.max(..counts)

  cetz.canvas(length: 1cm, {
    import cetz.draw: *

    let bar-width = 0.7
    let x-scale = 1.0
    let y-scale = 3.0 / max-count // normalize so tallest bar is 3cm

    // Bars
    for (i, count) in counts.enumerate() {
      let x = i * x-scale
      let h = count * y-scale
      rect(
        (x - bar-width / 2, 0),
        (x + bar-width / 2, h),
        fill: rgb("#4a7cb5"),
        stroke: rgb("#2d4d73") + 0.5pt,
      )
      // Count label above bar
      if count > 0 {
        content((x, h + 0.15), text(size: 6pt)[#count])
      }
    }

    // X axis
    line((-0.5, 0), (bins.len() * x-scale - 0.3, 0), stroke: 0.5pt)
    for (i, b) in bins.enumerate() {
      let x = i * x-scale
      content((x, -0.3), text(size: 7pt)[#b])
    }
    content((bins.len() * x-scale / 2 - 0.5, -0.7), text(size: 8pt)[Difficulty grade])

    // Y axis
    line((-0.5, 0), (-0.5, 3.2), stroke: 0.5pt)
    content((-0.5, 3.5), anchor: "south", text(size: 8pt)[Count])
  })
}
