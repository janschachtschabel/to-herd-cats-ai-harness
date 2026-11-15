/** Work that must finish before the session ends, e.g. sending what was typed in the
 *  live editor (review M2 R2). Features register a task; logout runs them all, but
 *  waits no longer than `timeoutMs`. */
type Task = () => Promise<void>

const tasks = new Set<Task>()

export function beforeLogout(task: Task): () => void {
  tasks.add(task)
  return () => void tasks.delete(task)
}

export async function runBeforeLogout(timeoutMs = 3000): Promise<void> {
  let timer: ReturnType<typeof setTimeout> | undefined
  const timeout = new Promise<void>((resolve) => (timer = setTimeout(resolve, timeoutMs)))
  await Promise.race([Promise.allSettled([...tasks].map((task) => task())), timeout])
  clearTimeout(timer)
}
