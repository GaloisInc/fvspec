import type { Attestation, Toolchain, Runner, Artifact, Limits, Track } from '@fvspec/common'

export function buildAttestation(input: {
  submissionId: number
  repoUrl: string
  commitSha: string
  trackId: Track
  toolchain?: Toolchain
  runner: Runner
  startedAt: string
  finishedAt: string
  artifacts: Artifact[]
  limits: Limits
}): Attestation {
  return {
    schema: 'https://lean4-bench.org/attestation/v1',
    ...input,
  }
}
