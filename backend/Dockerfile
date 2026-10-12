# One image for everything: the API Lambda, the scheduled-job Lambdas (which
# override CMD with their own handler), and local development under uvicorn.
FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

COPY app ${LAMBDA_TASK_ROOT}/app
COPY seed ${LAMBDA_TASK_ROOT}/seed

CMD ["app.main.handler"]
