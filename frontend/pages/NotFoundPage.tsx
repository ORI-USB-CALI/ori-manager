import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <main>
      <h1>404</h1>
      <p>The requested page was not found.</p>

      <Link to="/">Return to home</Link>
    </main>
  )
}
