import { useState, useEffect, useCallback } from 'react'
import JSZip from 'jszip'
import './App.css'
import { signIn, signOut, isAuthenticated, handleRedirectCallback } from './auth'
import { requestUploadUrl, uploadIntakeBundle, getStatus } from './api'

const INTAKE_CSV_HEADERS = [
  'MEMBER_ID', 'FIRST_NAME', 'LAST_NAME', 'DATE_OF_BIRTH',
  'ADDRESS', 'STATE_IN_ADDRESS', 'CITY_IN_ADDRESS',
  'ZIP_CODE_IN_ADDRESS', 'INSURANCE_PROVIDER',
]

// Turns the typed-in intake fields into the same one-row CSV the backend's
// write_patient_record Lambda already parses - so typing "wrong" details on
// purpose (to see a details-mismatch review) needs no backend change at all.
function toIntakeCsv(fields) {
  const row = [
    fields.memberId, fields.firstName, fields.lastName, fields.dateOfBirth,
    fields.address, fields.state, fields.city, fields.zip, fields.insuranceProvider,
  ]
  const escape = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`
  return `${INTAKE_CSV_HEADERS.join(',')}\n${row.map(escape).join(',')}\n`
}

// Bundles the intake fields (as CSV) and the two picked photos into a ZIP
// client-side, matching exactly what the backend's unzip Lambda expects
// (three files, suffix-matched names) - the patient never has to know a
// ZIP or a CSV is involved at all.
async function buildIntakeZip({ formFields, idFile, selfieFile }) {
  const zip = new JSZip()
  zip.file('bundle_intake.csv', toIntakeCsv(formFields))
  zip.file('bundle_id.png', idFile)
  zip.file('bundle_selfie.png', selfieFile)
  return zip.generateAsync({ type: 'blob' })
}

function App() {
  const [authed, setAuthed] = useState(false)
  const [ready, setReady] = useState(false)
  const [formFields, setFormFields] = useState({
    memberId: '',
    firstName: '',
    lastName: '',
    dateOfBirth: '',
    address: '',
    city: '',
    state: '',
    zip: '',
    insuranceProvider: '',
  })
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

  const updateField = useCallback((key) => (e) => {
    const value = e.target.value
    setFormFields((fields) => ({ ...fields, [key]: value }))
  }, [])

  const handleUpload = useCallback(async (e) => {
    e.preventDefault()
    const missingField = Object.entries(formFields).some(([, v]) => !v.trim())
    if (missingField || !idFile || !selfieFile) {
      setMessage({ type: 'error', text: 'Please fill in every field and attach both photos.' })
      return
    }
    setMessage({ type: 'pending', text: 'Preparing your documents…' })
    try {
      const zipBlob = await buildIntakeZip({ formFields, idFile, selfieFile })
      setMessage({ type: 'pending', text: 'Requesting secure upload URL…' })
      const { intake_id, upload_url } = await requestUploadUrl()
      setMessage({ type: 'pending', text: 'Uploading your documents…' })
      await uploadIntakeBundle(upload_url, zipBlob)
      setIntakeId(intake_id)
      setMessage({ type: 'success', text: `Intake submitted. Reference: ${intake_id}` })
    } catch {
      setMessage({ type: 'error', text: 'Upload failed. Please try again.' })
    }
  }, [formFields, idFile, selfieFile])

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
            Enter your intake details, then attach a photo of your ID and a selfie.
          </p>
          <form onSubmit={handleUpload} className="upload-form" autoComplete="off">
            <fieldset className="intake-fields">
              <legend>Intake details</legend>
              <p className="fieldset-hint">
                Type these to match your ID exactly — browser autofill is
                disabled here on purpose, since these fields are compared
                against what's printed on the document.
              </p>
              <label>
                Member ID
                <input type="text" autoComplete="hl-member-id" value={formFields.memberId} onChange={updateField('memberId')} />
              </label>
              <label>
                First name
                <input type="text" autoComplete="hl-first-name" value={formFields.firstName} onChange={updateField('firstName')} />
              </label>
              <label>
                Last name
                <input type="text" autoComplete="hl-last-name" value={formFields.lastName} onChange={updateField('lastName')} />
              </label>
              <label>
                Date of birth
                <input
                  type="text"
                  autoComplete="hl-dob"
                  placeholder="as printed on your ID, e.g. 01/12/1957"
                  value={formFields.dateOfBirth}
                  onChange={updateField('dateOfBirth')}
                />
              </label>
              <label>
                Address
                <input type="text" autoComplete="hl-address" value={formFields.address} onChange={updateField('address')} />
              </label>
              <label>
                City
                <input type="text" autoComplete="hl-city" value={formFields.city} onChange={updateField('city')} />
              </label>
              <label>
                State
                <input type="text" autoComplete="hl-state" value={formFields.state} onChange={updateField('state')} />
              </label>
              <label>
                ZIP code
                <input type="text" autoComplete="hl-zip" value={formFields.zip} onChange={updateField('zip')} />
              </label>
              <label>
                Insurance provider
                <input type="text" autoComplete="hl-insurance" value={formFields.insuranceProvider} onChange={updateField('insuranceProvider')} />
              </label>
            </fieldset>
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
