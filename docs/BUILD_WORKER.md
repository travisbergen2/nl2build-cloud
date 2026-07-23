# Build worker — GitHub Actions strategy

## Why
The original `build_worker.py` shelled out to `./gradlew` inside the worker
container. That never worked: the backend image installs no Android SDK/JDK/Gradle,
and the generated project had no Gradle wrapper JAR (its fallback `gradlew` called
itself recursively). It also required mounting a privileged `docker.sock`.

Instead we use **GitHub Actions as the build worker**:
- Runners already ship the Android SDK + JDK.
- Builds are free within plan limits — no build VM to host/pay for.
- The exact workflow pattern is already proven to produce real APKs in `NL2Build-`.

## Flow
```
codegen  → project.zip in object storage
build_worker:
  1. download project.zip
  2. create branch build/<job_id> in the build repo, commit files under generated/
  3. dispatch the "Build Generated App" workflow against that branch (input project_path=generated)
  4. poll the run to completion
  5. download the app-debug APK artifact → object storage
  6. enqueue signing
```

## Config (env)
| var | meaning |
|---|---|
| `GH_TOKEN` | PAT / app token with `repo` + `actions` scope |
| `GH_BUILD_REPO` | `owner/repo` holding `.github/workflows/build-generated.yml` |
| `GH_WORKFLOW` | workflow file name (default `build-generated.yml`) |

If `GH_TOKEN`/`GH_BUILD_REPO` are unset the worker fails loudly — it never fakes a build.

## Status (honest)
- **Proven in CI:** `.github/workflows/build-generated.yml` builds
  `examples/generated-sample` (a real codegen output) into a real `app-debug.apk`.
  That validates the *build* half — generated projects compile into real APKs.
- **Implemented, not yet runtime-verified:** the `build_worker.py` orchestration
  (commit → dispatch → poll → download). It needs a deployed backend with
  `GH_TOKEN` set to exercise end to end.

## Buildability fixes in codegen (`generator/android_template.py`)
- Framework XML theme instead of a missing `@style/Theme.AppCompat.Light`.
- Removed `@mipmap/ic_launcher` references (no icon resources were generated).
- Added an empty `proguard-rules.pro`.
- material3 resolved from the Compose BOM.
