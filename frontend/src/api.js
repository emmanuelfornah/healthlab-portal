// Client for the Cognito-protected Patient API.
import axios from 'axios';
import { getIdToken } from './auth';

const API_URL = import.meta.env.VITE_PATIENT_API_URL;

function authHeaders() {
  const token = getIdToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Request a presigned URL, then PUT the intake ZIP straight to S3.
export async function requestUploadUrl() {
  const res = await axios.post(
    `${API_URL}/intake/upload-url`,
    {},
    { headers: authHeaders() }
  );
  return res.data; // { intake_id, upload_url, expires_in }
}

export async function uploadIntakeBundle(uploadUrl, file) {
  await axios.put(uploadUrl, file, {
    headers: { 'Content-Type': 'application/zip' },
  });
}

export async function getStatus(intakeId) {
  const res = await axios.get(
    `${API_URL}/intake/${intakeId}/status`,
    { headers: authHeaders() }
  );
  return res.data;
}
