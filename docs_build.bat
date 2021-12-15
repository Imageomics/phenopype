@echo off
@echo .doctrees > docs/.gitignore

if "%*"=="-d" (
	rmdir /Q /S _temp
)

sphinx-multibuild -c docs_source -i docs_source -i ../phenopype-tutorials\tutorials  -s _temp/docs -o docs -a

if "%*"=="-o" (
	cd docs
	rmdir ".git" /S /Q
	git init
	@echo .doctrees > .gitignore
	git add .
	git commit -m "- generated dynamically with sphinx -"
	git remote add origin https://github.com/phenopype/phenopype-docs
	git push --force origin main
	cd ..
)
