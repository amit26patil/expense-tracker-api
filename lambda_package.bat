@echo off
setlocal

echo ==========================================
echo Building AWS Lambda package for FastAPI
echo ==========================================

REM Remove old package folder
if exist package (
    echo Removing existing package folder...
    rmdir /s /q package
)

mkdir package

echo.
echo Installing dependencies using Lambda-compatible Docker image...
docker run --rm ^
-v "%cd%:/var/task" ^
public.ecr.aws/sam/build-python3.14 ^
pip install -r requirements.txt -t package

if %ERRORLEVEL% NEQ 0 (
    echo Docker build failed.
    exit /b 1
)

echo.
echo Copying application files...

copy main.py package\
copy lambda_handler.py package\
copy expense-tracker-500203-1d10858a70af.json package\
xcopy /E /I /Y app package\app

echo.
echo Creating deployment zip...

if exist lambda-package.zip del lambda-package.zip

tar -a -c -f lambda-package.zip -C package .

if %ERRORLEVEL% NEQ 0 (
    echo ZIP creation failed.
    exit /b 1
)

echo.
echo ==========================================
echo Build completed successfully!
echo Output: lambda-package.zip
echo ==========================================

endlocal