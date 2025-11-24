import { redirect } from 'next/navigation'

export default function DatasetIndexPage() {
  // Redirect to the first sample (ID 341)
  redirect('/dataset/341')
}
