import { useId, type ReactNode } from 'react'

/** One field: its label, and the control (`editable`) or just the value. */
export function FieldRow({
  label,
  editable = true,
  children,
}: {
  label: string
  editable?: boolean
  children: (id: string) => ReactNode
}) {
  const id = useId()
  const className = 'text-xs font-medium text-muted-foreground'
  return (
    <div className="flex flex-col gap-1">
      {editable ? (
        <label htmlFor={id} className={className}>
          {label}
        </label>
      ) : (
        <span id={`${id}-label`} className={className}>
          {label}
        </span>
      )}
      {children(id)}
    </div>
  )
}
