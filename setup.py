from setuptools import setup, find_packages

setup(
    name="datamatrix-quality-scanner",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "opencv-python>=4.8.0",
        "pylibdmtx>=0.1.10",
        "numpy>=1.24.0",
        "PyQt6>=6.5.0",
        "Pillow>=10.0.0",
    ],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "dm-scanner=main:main",
        ],
    },
    author="Industrial Vision Systems",
    description="Data Matrix Quality Scanner according to GOST R 57302-2016",
)