import uvicorn
from fastapi import FastAPI

from models.ads import AdRequest, AdResponse
from routers.users import root_router
from routers.users import router as user_router

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/predict", response_model=AdResponse)
async def predict(ad: AdRequest):

    if ad.is_verified_seller:
        result = True
    else:
        result = ad.images_qty > 0

    return AdResponse(is_allowed=result)


app.include_router(user_router, prefix="/users")
app.include_router(root_router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
