import { useState, useEffect, useCallback } from 'react'
import JSZip from 'jszip'
import './App.css'
import { signIn, signOut, isAuthenticated, handleRedirectCallback } from './auth'
import { requestUploadUrl, uploadIntakeBundle, getStatus } from './api'

// Bundles the three picked files into a ZIP client-side, matching exactly
// what the backend's unzip Lambda expects (three files, suffix-matched
// names) - the patient never has to know a ZIP is involved at all.
async function buildIntakeZip({ formFile, idFile, selfieFile }) {
  const zip = new JSZip()
  zip.file('bundle_intake.csv', formFile)
  zip.file('bundle_id.png', idFile)
  zip.file('bundle_selfie.png', selfieFile)
  return zip.generateAsync({ type: 'blob' })
}

function App() {
  const [authed, setAuthed] = useState(false)
  const [ready, setReady] = useState(false)
  const [formFile, setFormFile] = useState(null)
  const [idFile, setIdFile] = useState(null)
  const [selfieFile, setSelfieFile] = useState(null)
  const [intakeId, setIntakeId] = useState(null)
  const [status, setStatus] = useState(null)
  const [message, setMessage] = useState(null)

  // On load, complete the Cognito redirect (if any) then check auth state.
  useEffect(() => {
    (async () => {
      try {
        await handleRedirectCallback()
      } catch {
        setMessage({ type: 'error', text: 'Sign-in failed. Please try again.' })
      }
      setAuthed(isAuthenticated())
      setReady(true)
    })()
  }, [])

  const handleUpload = useCallback(async (e) => {
    e.preventDefault()
    if (!formFile || !idFile || !selfieFile) {
      setMessage({ type: 'error', text: 'Please choose all three files.' })
      return
    }
    setMessage({ type: 'pending', text: 'Preparing your documents…' })
    try {
      const zipBlob = await buildIntakeZip({ formFile, idFile, selfieFile })
      setMessage({ type: 'pending', text: 'Requesting secure upload URL…' })
      const { intake_id, upload_url } = await requestUploadUrl()
      setMessage({ type: 'pending', text: 'Uploading your documents…' })
      await uploadIntakeBundle(upload_url, zipBlob)
      setIntakeId(intake_id)
      setMessage({ type: 'success', text: `Intake submitted. Reference: ${intake_id}` })
    } catch {
      setMessage({ type: 'error', text: 'Upload failed. Please try again.' })
    }
  }, [formFile, idFile, selfieFile])

  const checkStatus = useCallback(async () => {
    if (!intakeId) return
    try {
      setStatus(await getStatus(intakeId))
    } catch {
      setMessage({ type: 'error', text: 'Could not fetch status.' })
    }
  }, [intakeId])

  if (!ready) return <main className="app"><p>Loading…</p></main>

  return (
    <main className="app">
      <header className="banner">
        <h1>🏥 HealthLab Portal</h1>
        <p className="tagline">Secure patient onboarding & identity verification</p>
        {authed && (
          <button className="link-btn" onClick={signOut}>Sign out</button>
        )}
      </header>

      {!authed ? (
        <section className="card">
          <h2>Welcome</h2>
          <p>Sign in to begin your patient onboarding.</p>
          <button className="primary-btn" onClick={signIn}>Sign in</button>
        </section>
      ) : (
        <section className="card">
          <h2>Submit intake documents</h2>
          <p>
            Upload your intake form, a photo of your ID, and a selfie below.
          </p>
          <form onSubmit={handleUpload} className="upload-form">
            <label>
              Intake form (CSV)
              <input
                type="file"
                accept=".csv"
                onChange={(e) => setFormFile(e.target.files[0])}
              />
            </label>
            <label>
              ID photo
              <input
                type="file"
                accept="image/*"
                capture="environment"
                onChange={(e) => setIdFile(e.target.files[0])}
              />
            </label>
            <label>
              Selfie
              <input
                type="file"
                accept="image/*"
                capture="user"
                onChange={(e) => setSelfieFile(e.target.files[0])}
              />
            </label>
            <button className="primary-btn" type="submit">Submit intake</button>
          </form>

          {intakeId && (
            <div className="status-panel">
              <button className="secondary-btn" onClick={checkStatus}>
                Refresh status
              </button>
              {status && (
                <ul className="status-list">
                  <li>Status: <strong>{status.status}</strong></li>
                  <li>Identity verified: {String(status.identity_verified)}</li>
                  <li>Details match: {String(status.details_match)}</li>
                  <li>Eligibility verified: {String(status.eligibility_verified)}</li>
                </ul>
              )}
            </div>
          )}
        </section>
      )}

      {message && (
        <p className={`message message-${message.type}`}>{message.text}</p>
      )}

      <footer className="footer">
        <p>© {new Date().getFullYear()} HealthLab Portal. Demonstration project.</p>
      </footer>
    </main>
  )
}

export default App
