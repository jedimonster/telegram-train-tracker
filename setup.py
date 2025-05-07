"""Setup script for the train bot package."""

from setuptools import setup, find_packages

setup(
    name="train-bot",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "python-telegram-bot>=20.0",
        "python-dotenv>=0.19.0",
        "requests>=2.26.0",
    ],
    python_requires=">=3.7",
    entry_points={
        "console_scripts": [
            "train-bot=run:main",
        ],
    },
    author="Itai Azulay",
    description="Telegram bot for checking train information and subscribing to updates",
    keywords="telegram,bot,train,israel-railways",
    project_urls={
        "Source": "https://github.com/yourusername/train-bot",
    },
)
