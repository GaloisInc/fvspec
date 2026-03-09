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
