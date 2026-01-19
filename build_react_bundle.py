"""
Build React PDF Templates Bundle

Compiles React PDF template components into a standalone JavaScript bundle
for embedding in headless browser PDF generation.
"""

import subprocess
import os
import sys
from pathlib import Path
import shutil


def build_pdf_templates():
    """
    Build React PDF template components into a standalone bundle.
    Uses esbuild for fast bundling.
    """
    # Determine paths
    backend_dir = Path(__file__).parent
    frontend_dir = backend_dir.parent / "aneya-frontend"

    # Check if frontend directory exists
    if not frontend_dir.exists():
        print(f"❌ Frontend directory not found at: {frontend_dir}")
        print("   Make sure both aneya-backend and aneya-frontend are in the same parent directory.")
        sys.exit(1)

    # Navigate to frontend directory
    os.chdir(frontend_dir)

    # Check if node_modules exists
    if not (frontend_dir / "node_modules").exists():
        print("⚠️  node_modules not found. Running npm install...")
        subprocess.run(["npm", "install"], check=True)

    # Build PDF templates bundle using esbuild
    print("🔨 Building PDF templates bundle...")

    try:
        result = subprocess.run([
            "npx", "esbuild",
            "src/components/pdf-templates/index.tsx",
            "--bundle",
            "--outfile=dist/pdf-templates-bundle.js",
            "--format=iife",
            "--global-name=PdfTemplates",
            # NOTE: Not using --external:react to bundle React directly (browser compatibility)
            "--jsx=automatic",
            "--target=es2020",
            "--minify"
        ], check=True, capture_output=True, text=True)

        print(result.stdout)
        if result.stderr:
            print("⚠️  Warnings:", result.stderr)

    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        print(f"   stdout: {e.stdout}")
        print(f"   stderr: {e.stderr}")
        sys.exit(1)

    # Create static directory in backend if it doesn't exist
    backend_static_dir = backend_dir / "static"
    backend_static_dir.mkdir(exist_ok=True)

    # Copy bundle to backend static directory
    bundle_source = frontend_dir / "dist" / "pdf-templates-bundle.js"
    bundle_dest = backend_static_dir / "pdf-templates-bundle.js"

    if not bundle_source.exists():
        print(f"❌ Bundle file not created at: {bundle_source}")
        sys.exit(1)

    shutil.copy2(bundle_source, bundle_dest)

    # Get bundle size
    bundle_size_kb = bundle_dest.stat().st_size / 1024

    print(f"✅ PDF templates bundle created successfully!")
    print(f"   Source: {bundle_source}")
    print(f"   Destination: {bundle_dest}")
    print(f"   Size: {bundle_size_kb:.2f} KB")


def build_doctor_report_card_bundle():
    """
    Build DoctorReportCard component into standalone bundle for PDF generation.
    """
    backend_dir = Path(__file__).parent
    frontend_dir = backend_dir.parent / "aneya-frontend"

    if not frontend_dir.exists():
        print(f"❌ Frontend directory not found at: {frontend_dir}")
        return False

    os.chdir(frontend_dir)

    print("🔨 Building DoctorReportCard bundle...")

    try:
        result = subprocess.run([
            "npx", "esbuild",
            "src/components/doctor-report-card/bundle-entry.tsx",
            "--bundle",
            "--outfile=dist/doctor-report-card-bundle.js",
            "--format=iife",
            "--global-name=DoctorReportCardBundle",
            "--jsx=automatic",
            "--target=es2020",
            "--minify"
        ], check=True, capture_output=True, text=True)

        print(result.stdout)
        if result.stderr:
            print("⚠️  Warnings:", result.stderr)

    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        print(f"   stderr: {e.stderr}")
        return False

    # Copy to backend static directory
    bundle_source = frontend_dir / "dist" / "doctor-report-card-bundle.js"
    backend_static_dir = backend_dir / "static"
    backend_static_dir.mkdir(exist_ok=True)
    bundle_dest = backend_static_dir / "doctor-report-card-bundle.js"

    if not bundle_source.exists():
        print(f"❌ Bundle file not created at: {bundle_source}")
        return False

    shutil.copy2(bundle_source, bundle_dest)

    bundle_size_kb = bundle_dest.stat().st_size / 1024
    print(f"✅ DoctorReportCard bundle created: {bundle_size_kb:.2f} KB")
    return True


def verify_bundle():
    """
    Verify the bundle was created correctly.
    """
    backend_dir = Path(__file__).parent
    bundle_path = backend_dir / "static" / "pdf-templates-bundle.js"

    if not bundle_path.exists():
        print("❌ Bundle verification failed: File not found")
        return False

    # Check if bundle contains expected exports
    with open(bundle_path, 'r') as f:
        bundle_content = f.read()

    expected_exports = [
        "PdfConsultationForm",
        "PdfAnalysisReport",
        "PdfTableRenderer"
    ]

    missing_exports = []
    for export_name in expected_exports:
        if export_name not in bundle_content:
            missing_exports.append(export_name)

    if missing_exports:
        print(f"⚠️  Bundle may be incomplete. Missing: {', '.join(missing_exports)}")
        return False

    print("✅ Bundle verification passed")
    return True


if __name__ == '__main__':
    print("=" * 60)
    print("Building React PDF Bundles")
    print("=" * 60)
    print()

    try:
        # Build PDF templates bundle (PdfConsultationForm, PdfAnalysisReport)
        print("1. Building PDF templates bundle...")
        build_pdf_templates()
        print()

        # Verify the bundle
        verify_bundle()
        print()

        # Build DoctorReportCard bundle
        print("2. Building DoctorReportCard bundle...")
        success = build_doctor_report_card_bundle()
        print()

        if success:
            print("=" * 60)
            print("✅ All bundles built successfully!")
            print("=" * 60)
        else:
            print("=" * 60)
            print("❌ DoctorReportCard build failed")
            print("=" * 60)
            sys.exit(1)

    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ Build failed: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        sys.exit(1)
