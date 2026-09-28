buildscript {
    ext.kotlin_version = '1.9.0'
    repositories {
        google()
        mavenCentral()
    }

    dependencies {
        classpath "org.jetbrains.kotlin:kotlin-gradle-plugin:$kotlin_version"
    }
}

allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

// Add this block to force all subprojects (including plugins) to use SDK 34
subprojects {
    afterEvaluate { project ->
        if (project.hasProperty('android')) {
            project.android {
                compileSdkVersion 34
                if (project.android.hasProperty('defaultConfig')) {
                    project.android.defaultConfig {
                        targetSdkVersion 34
                    }
                }
            }
        }
    }
}
