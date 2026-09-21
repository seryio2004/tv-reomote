const player = document.getElementById("player");
const statusElement = document.getElementById("status");

let socket;

function connectWebSocket() {
    const protocol =
        window.location.protocol === "https:"
            ? "wss"
            : "ws";

    socket = new WebSocket(
        `${protocol}://${window.location.host}/ws`
    );

    socket.onopen = () => {
        console.log("WebSocket conectado");
        socket.send("player-connected");
    };

    socket.onmessage = async (event) => {
        const message = JSON.parse(event.data);

        try {
            switch (message.type) {

                case "play":
                    statusElement.textContent = "Cargando...";
                    player.src = message.url;
                    player.load();

                    await player.play();

                    statusElement.textContent = "";
                    break;

                case "pause":
                    player.pause();
                    break;

                case "resume":
                    await player.play();
                    break;

                case "stop":
                    player.pause();
                    player.removeAttribute("src");
                    player.load();

                    statusElement.textContent = "TV Remote";
                    break;

                case "seek":
                    if (
                        Number.isFinite(player.duration) ||
                        player.readyState > 0
                    ) {
                        player.currentTime =
                            Math.max(
                                0,
                                player.currentTime + message.seconds
                            );
                    }
                    break;

                case "volume":
                    player.volume = Math.max(
                        0,
                        Math.min(1, message.value)
                    );
                    break;
            }

        } catch (error) {
            console.error(error);

            statusElement.textContent =
                "No se pudo reproducir el contenido";
        }
    };

    socket.onclose = () => {
        statusElement.textContent =
            "Reconectando con el servidor...";

        setTimeout(connectWebSocket, 1500);
    };

    socket.onerror = (error) => {
        console.error("WebSocket error:", error);
    };
}

connectWebSocket();
