export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...options,
    credentials: 'include',
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
  })
  if (!response.ok) {
    const result: { detail?: string | Array<{ loc?: Array<string | number>; msg?: string }> } =
      await response.json().catch(() => ({}))
    const detail = Array.isArray(result.detail)
      ? result.detail.map((item) => `${item.loc?.join('.') ?? 'Input'}: ${item.msg ?? 'invalid value'}`).join('; ')
      : result.detail
    throw new ApiError(detail || `Request failed (${response.status}).`, response.status)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
