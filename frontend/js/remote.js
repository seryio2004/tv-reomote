const urlInput =
    document.getElementById("url");

const messageElement =
    document.getElementById("message");

const volumeInput =
    document.getElementById("volume");

const volumeValue =
    document.getElementById("volume-value");


async function post(path, body = null) {

    const options = {
        method: "POST",
        headers: {}
    };

    if (body !== null) {

        options.headers["Content-Type"] =
            "application/json";

        options.body =
            JSON.stringify(body);
    }

    const response =
        await fetch(path, options);

    if (!response.ok) {
        throw new Error(
            `HTTP ${response.status}`
        );
    }

    return response.json();
}


function showMessage(text) {

    messageElement.textContent = text;

    window.clearTimeout(
        showMessage.timeout
    );

    showMessage.timeout =
        window.setTimeout(() => {
            messageElement.textContent = "";
        }, 2000);
}


document
    .getElementById("play")
    .addEventListener("click", async () => {

        const url = urlInput.value.trim();

        if (!url) {
            showMessage(
                "Introduce una URL."
            );

            return;
        }

        try {

            await post(
                "/api/play",
                { url }
            );

            showMessage(
                "Enviado a la TV."
            );

        } catch (error) {

            console.error(error);

            showMessage(
                "Error al enviar el vídeo."
            );
        }
    });


document
    .getElementById("pause")
    .addEventListener("click", async () => {

        await post("/api/pause");

    });


document
    .getElementById("resume")
    .addEventListener("click", async () => {

        await post("/api/resume");

    });


document
    .getElementById("back")
    .addEventListener("click", async () => {

        await post(
            "/api/seek",
            { seconds: -10 }
        );

    });


document
    .getElementById("forward")
    .addEventListener("click", async () => {

        await post(
            "/api/seek",
            { seconds: 10 }
        );

    });


document
    .getElementById("stop")
    .addEventListener("click", async () => {

        await post("/api/stop");

    });


volumeInput.addEventListener(
    "input",
    async () => {

        const value =
            Number(volumeInput.value);

        volumeValue.textContent =
            `${value}%`;

        await post(
            "/api/volume",
            {
                value: value / 100
            }
        );
    }
);
