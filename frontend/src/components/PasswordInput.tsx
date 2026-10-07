import { type ComponentProps, useState } from 'react'

interface PasswordInputProps
  extends Omit<ComponentProps<'input'>, 'id' | 'type'> {
  id: string
  label: string
}

export function PasswordInput({
  id,
  label,
  className,
  disabled,
  ...props
}: PasswordInputProps) {
  const [visible, setVisible] = useState(false)
  const actionLabel = visible ? 'Ocultar contraseña' : 'Mostrar contraseña'

  return (
    <>
      <label className="form-label" htmlFor={id}>
        {label}
      </label>
      <div className="password-input-wrapper">
        <input
          {...props}
          id={id}
          type={visible ? 'text' : 'password'}
          className={`form-control password-input ${className ?? ''}`}
          disabled={disabled}
        />
        <button
          type="button"
          className="password-toggle"
          aria-label={actionLabel}
          aria-pressed={visible}
          aria-controls={id}
          disabled={disabled}
          onClick={() => setVisible((current) => !current)}
        >
          {visible ? <EyeOffIcon /> : <EyeIcon />}
        </button>
      </div>
    </>
  )
}

function EyeIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />
      <circle cx="12" cy="12" r="2.5" />
    </svg>
  )
}

function EyeOffIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M3 3l18 18" />
      <path d="M10.6 6.1A10.8 10.8 0 0 1 12 6c6 0 9.5 6 9.5 6a16 16 0 0 1-2.4 3.1M6.2 6.2A16 16 0 0 0 2.5 12s3.5 6 9.5 6c1.4 0 2.7-.3 3.8-.8" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
    </svg>
  )
}
