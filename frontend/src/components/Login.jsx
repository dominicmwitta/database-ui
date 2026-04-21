import { useState } from 'react';
import { Lock, User, Eye, EyeOff } from 'lucide-react';
import { BRAND } from '../theme';
import { login } from '../api/client';

const field = {
  width: '100%',
  padding: '9px 12px',
  fontSize: 13,
  border: `1px solid ${BRAND.mildGrey}`,
  borderRadius: 4,
  outline: 'none',
  fontFamily: 'inherit',
  boxSizing: 'border-box',
};

export default function Login({ onLogin }) {
  const [form, setForm] = useState({
    username: '',
    password: '',
  });
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login({ ...form, port: Number(form.port) });
      onLogin();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: `linear-gradient(135deg, ${BRAND.navy} 0%, #0A1F44 60%, #2B2B2B 100%)`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <form onSubmit={handleSubmit} style={{
        background: '#fff', borderRadius: 8, padding: '40px 36px',
        width: 360, boxShadow: '0 20px 60px rgba(0,0,0,0.4)',
      }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ fontSize: 9, color: BRAND.midGrey, letterSpacing: '0.22em', textTransform: 'uppercase', fontWeight: 600 }}>
            Bank of Tanzania
          </div>
          <div style={{ fontSize: 18, color: BRAND.navy, marginTop: 8, fontWeight: 600, fontFamily: 'Georgia, serif' }}>
            Statistics
          </div>
          <div style={{ fontSize: 11, color: BRAND.midGrey, marginTop: 4 }}>Sign in to continue</div>
        </div>

        {/* Username */}
        <div style={{ marginBottom: 14 }}>
          <label style={{ fontSize: 11, fontWeight: 600, color: BRAND.midGrey, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Username
          </label>
          <div style={{ position: 'relative', marginTop: 4 }}>
            <User size={14} style={{ position: 'absolute', left: 10, top: 11, color: BRAND.midGrey }} />
            <input style={{ ...field, paddingLeft: 32 }} value={form.username} onChange={set('username')}
              placeholder="DB username" required autoComplete="username" />
          </div>
        </div>

        {/* Password */}
        <div style={{ marginBottom: 14 }}>
          <label style={{ fontSize: 11, fontWeight: 600, color: BRAND.midGrey, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Password
          </label>
          <div style={{ position: 'relative', marginTop: 4 }}>
            <Lock size={14} style={{ position: 'absolute', left: 10, top: 11, color: BRAND.midGrey }} />
            <input style={{ ...field, paddingLeft: 32, paddingRight: 36 }}
              type={showPwd ? 'text' : 'password'}
              value={form.password} onChange={set('password')}
              placeholder="••••••••" required autoComplete="current-password" />
            <button type="button" onClick={() => setShowPwd(!showPwd)}
              style={{ position: 'absolute', right: 10, top: 9, background: 'none', border: 'none', cursor: 'pointer', color: BRAND.midGrey }}>
              {showPwd ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          </div>
        </div>

        {error && (
          <div style={{ background: '#fff5f5', border: '1px solid #fca5a5', borderRadius: 4, padding: '8px 12px', fontSize: 12, color: '#dc2626', marginBottom: 14 }}>
            {error}
          </div>
        )}

        <button type="submit" disabled={loading} style={{
          width: '100%', padding: '11px', background: loading ? BRAND.midGrey : BRAND.navy,
          color: '#fff', border: 'none', borderRadius: 4, fontSize: 13, fontWeight: 600,
          letterSpacing: '0.04em', cursor: loading ? 'not-allowed' : 'pointer', fontFamily: 'inherit',
        }}>
          {loading ? 'Connecting…' : 'SIGN IN'}
        </button>
      </form>
    </div>
  );
}
