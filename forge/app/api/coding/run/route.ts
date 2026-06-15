import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { spawn } from 'node:child_process'
import { NextResponse } from 'next/server'
import { getCodingProblemBySlug, type CodingTestCase } from '@/lib/coding-problems'

export const runtime = 'nodejs'

type RunRequest = {
  slug?: string
  code?: string
}

type PythonResult = {
  status: 'passed' | 'failed' | 'error'
  passed: number
  total: number
  tests: {
    name: string
    status: 'passed' | 'failed' | 'error'
    input: unknown[]
    expected: unknown
    actual?: unknown
    error?: string
  }[]
  error?: string
}

export async function POST(request: Request) {
  const body = await request.json().catch(() => ({})) as RunRequest
  const slug = body.slug
  const code = body.code

  if (!slug || !code) {
    return NextResponse.json({ error: 'Missing problem slug or Python code.' }, { status: 400 })
  }

  const problem = getCodingProblemBySlug(slug)
  if (!problem || !problem.judgeReady) {
    return NextResponse.json({ error: 'This problem does not have a configured Forge judge yet.' }, { status: 404 })
  }

  if (code.length > 20000) {
    return NextResponse.json({ error: 'Submission is too large for this prototype judge.' }, { status: 400 })
  }

  const workdir = await mkdtemp(path.join(tmpdir(), 'forge-python-'))

  try {
    await writeFile(path.join(workdir, 'solution.py'), code, 'utf8')
    await writeFile(path.join(workdir, 'runner.py'), buildRunner(problem.functionName, problem.tests), 'utf8')
    const result = await runPython(workdir)
    return NextResponse.json(result, { status: result.status === 'error' ? 400 : 200 })
  } finally {
    await rm(workdir, { recursive: true, force: true }).catch(() => undefined)
  }
}

function runPython(workdir: string) {
  return new Promise<PythonResult>((resolve) => {
    const child = spawn('python3', ['-I', 'runner.py'], {
      cwd: workdir,
      env: {
        ...process.env,
        PYTHONIOENCODING: 'utf-8',
      },
      stdio: 'pipe',
    })
    let stdout = ''
    let stderr = ''
    const timeout = setTimeout(() => {
      child.kill('SIGKILL')
      resolve({
        status: 'error',
        passed: 0,
        total: 0,
        tests: [],
        error: 'Execution timed out after 3 seconds.',
      })
    }, 3000)

    child.stdout.on('data', (chunk) => {
      stdout += String(chunk)
      if (stdout.length > 60000) stdout = stdout.slice(-60000)
    })

    child.stderr.on('data', (chunk) => {
      stderr += String(chunk)
      if (stderr.length > 60000) stderr = stderr.slice(-60000)
    })

    child.on('error', (error) => {
      clearTimeout(timeout)
      resolve({
        status: 'error',
        passed: 0,
        total: 0,
        tests: [],
        error: error.message,
      })
    })

    child.on('close', () => {
      clearTimeout(timeout)
      const text = stdout.trim()
      if (!text) {
        resolve({
          status: 'error',
          passed: 0,
          total: 0,
          tests: [],
          error: stderr.trim() || 'Python produced no judge output.',
        })
        return
      }

      try {
        resolve(JSON.parse(text) as PythonResult)
      } catch {
        resolve({
          status: 'error',
          passed: 0,
          total: 0,
          tests: [],
          error: stderr.trim() || text.slice(0, 1200),
        })
      }
    })
  })
}

function buildRunner(functionName: string, tests: CodingTestCase[]) {
  return `import importlib.util
import json
import math
import traceback

TESTS = ${JSON.stringify(tests)}
FUNCTION_NAME = ${JSON.stringify(functionName)}

def normalize(value, compare):
    if compare == "sort":
        return sorted(value)
    if compare == "sortNested":
        return [sorted(item) for item in value]
    return value

def matches(actual, expected, compare):
    if compare == "float":
        try:
            return math.isclose(float(actual), float(expected), rel_tol=1e-6, abs_tol=1e-6)
        except Exception:
            return False
    try:
        return normalize(actual, compare) == normalize(expected, compare)
    except Exception:
        return False

def json_safe(value):
    try:
        json.dumps(value)
        return value
    except Exception:
        return repr(value)

try:
    spec = importlib.util.spec_from_file_location("solution", "solution.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, FUNCTION_NAME)
except Exception:
    print(json.dumps({
        "status": "error",
        "passed": 0,
        "total": len(TESTS),
        "tests": [],
        "error": traceback.format_exc(limit=6),
    }))
    raise SystemExit(0)

results = []
passed = 0

for test in TESTS:
    compare = test.get("compare", "exact")
    try:
        actual = fn(*test["input"])
        ok = matches(actual, test["expected"], compare)
        if ok:
            passed += 1
        results.append({
            "name": test["name"],
            "status": "passed" if ok else "failed",
            "input": test["input"],
            "expected": test["expected"],
            "actual": json_safe(actual),
        })
    except Exception:
        results.append({
            "name": test["name"],
            "status": "error",
            "input": test["input"],
            "expected": test["expected"],
            "error": traceback.format_exc(limit=4),
        })

print(json.dumps({
    "status": "passed" if passed == len(TESTS) else "failed",
    "passed": passed,
    "total": len(TESTS),
    "tests": results,
}))
`
}
