export const PASSWORD_POLICY_MESSAGE =
  'La contraseña debe tener al menos 8 caracteres e incluir una mayúscula, una minúscula, un número y un carácter especial.'

export function passwordPolicyError(password: string): string | null {
  const hasUppercase = /\p{Lu}/u.test(password)
  const hasLowercase = /\p{Ll}/u.test(password)
  const hasNumber = /\p{N}/u.test(password)
  const hasSpecial = [...password].some(
    (character) =>
      !/[\p{L}\p{N}]/u.test(character) && !/\s/u.test(character),
  )

  if (
    [...password].length < 8 ||
    !hasUppercase ||
    !hasLowercase ||
    !hasNumber ||
    !hasSpecial
  ) {
    return PASSWORD_POLICY_MESSAGE
  }
  return null
}
