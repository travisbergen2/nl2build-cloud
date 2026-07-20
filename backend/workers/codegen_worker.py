"""
Code Generation Worker (Phase 2 & 7)
Generates Android project from specification
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from database import SessionLocal
from models import Job, JobStatus
from queue import enqueue_build_job
from storage import storage
import io
import zipfile


def generate_code(job_id: str) -> None:
    db: Session = SessionLocal()

    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise Exception(f"Job {job_id} not found")

        job.status = JobStatus.CODEGEN
        job.current_step = "codegen"
        db.commit()

        project_zip = generate_android_project(job.spec, job.package_name)

        key = f"{job_id}/project.zip"
        storage.upload_bytes(project_zip, key)

        job.current_step = "codegen_complete"
        db.commit()

        enqueue_build_job(job_id)

        print(f"Code generated for job {job_id}")

    except Exception as e:
        print(f"Code generation failed for job {job_id}: {str(e)}")
        job.status = JobStatus.FAILED
        job.errors = f"Code generation error: {str(e)}"
        db.commit()
        raise

    finally:
        db.close()


def generate_android_project(spec: dict, package_name: str) -> bytes:
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        package_path = package_name.replace('.', '/')

        zip_file.writestr('settings.gradle.kts', generate_settings_gradle(spec))
        zip_file.writestr('build.gradle.kts', generate_project_build_gradle())
        zip_file.writestr('app/build.gradle.kts', generate_app_build_gradle(spec, package_name))
        zip_file.writestr(
            'app/src/main/AndroidManifest.xml',
            generate_manifest(spec, package_name)
        )
        zip_file.writestr(
            f'app/src/main/java/{package_path}/MainActivity.kt',
            generate_main_activity(spec, package_name)
        )
        zip_file.writestr(
            f'app/src/main/java/{package_path}/ui/MainScreen.kt',
            generate_main_screen(spec, package_name)
        )
        zip_file.writestr('gradle.properties', generate_gradle_properties())
        zip_file.writestr('gradle/wrapper/gradle-wrapper.properties',
                         generate_gradle_wrapper_properties())

    zip_buffer.seek(0)
    return zip_buffer.read()


def generate_settings_gradle(spec: dict) -> str:
    app_name = spec.get('app_name', 'MyApp').replace(' ', '')

    return f"""pluginManagement {{
    repositories {{
        google()
        mavenCentral()
        gradlePluginPortal()
    }}
}}
dependencyResolutionManagement {{
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {{
        google()
        mavenCentral()
    }}
}}

rootProject.name = "{app_name}"
include(":app")
"""


def generate_project_build_gradle() -> str:
    return """plugins {
    id("com.android.application") version "8.1.4" apply false
    id("org.jetbrains.kotlin.android") version "1.9.20" apply false
}
"""


def generate_app_build_gradle(spec: dict, package_name: str) -> str:
    min_sdk = spec.get('min_sdk', 24)
    target_sdk = spec.get('target_sdk', 34)
    deps = spec.get('dependencies', {})

    compose_version = deps.get('compose', '1.5.4')
    material3_version = deps.get('compose_material3', '1.1.2')

    return f"""plugins {{
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}}

android {{
    namespace = "{package_name}"
    compileSdk = {target_sdk}

    defaultConfig {{
        applicationId = "{package_name}"
        minSdk = {min_sdk}
        targetSdk = {target_sdk}
        versionCode = 1
        versionName = "1.0"

        vectorDrawables {{
            useSupportLibrary = true
        }}
    }}

    buildTypes {{
        release {{
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }}
    }}

    compileOptions {{
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }}

    kotlinOptions {{
        jvmTarget = "1.8"
    }}

    buildFeatures {{
        compose = true
    }}

    composeOptions {{
        kotlinCompilerExtensionVersion = "{compose_version}"
    }}

    packaging {{
        resources {{
            excludes += "/META-INF/{{AL2.0,LGPL2.1}}"
        }}
    }}
}}

dependencies {{
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.6.2")
    implementation("androidx.activity:activity-compose:1.8.1")
    implementation(platform("androidx.compose:compose-bom:2023.10.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3:{material3_version}")
}}
"""


def generate_manifest(spec: dict, package_name: str) -> str:
    app_name = spec.get('app_name', 'MyApp')
    permissions = spec.get('permissions', [])

    permissions_xml = '\n    '.join([f'<uses-permission android:name="android.permission.{p}" />'
                                     for p in permissions])

    return f"""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    {permissions_xml}

    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:label="{app_name}"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:supportsRtl="true"
        android:theme="@style/Theme.AppCompat.Light">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:theme="@style/Theme.AppCompat.Light">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
"""


def generate_main_activity(spec: dict, package_name: str) -> str:
    return f"""package {package_name}

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import {package_name}.ui.MainScreen

class MainActivity : ComponentActivity() {{
    override fun onCreate(savedInstanceState: Bundle?) {{
        super.onCreate(savedInstanceState)
        setContent {{
            MaterialTheme {{
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {{
                    MainScreen()
                }}
            }}
        }}
    }}
}}
"""


def generate_main_screen(spec: dict, package_name: str) -> str:
    app_name = spec.get('app_name', 'MyApp')
    description = spec.get('description', 'Welcome to the app')

    return f"""package {package_name}.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen() {{
    Scaffold(
        topBar = {{
            TopAppBar(
                title = {{ Text("{app_name}") }},
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                    titleContentColor = MaterialTheme.colorScheme.onPrimaryContainer
                )
            )
        }}
    ) {{ padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {{
            Text(
                text = "{app_name}",
                style = MaterialTheme.typography.headlineLarge,
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(16.dp))

            Text(
                text = "{description}",
                style = MaterialTheme.typography.bodyLarge,
                textAlign = TextAlign.Center,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            Spacer(modifier = Modifier.height(32.dp))

            Button(onClick = {{ /* TODO: Implement action */ }}) {{
                Text("Get Started")
            }}
        }}
    }}
}}
"""


def generate_gradle_properties() -> str:
    return """org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
android.useAndroidX=true
android.enableJetifier=true
kotlin.code.style=official
android.nonTransitiveRClass=true
"""


def generate_gradle_wrapper_properties() -> str:
    return """distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\\://services.gradle.org/distributions/gradle-8.2-bin.zip
networkTimeout=10000
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
"""
