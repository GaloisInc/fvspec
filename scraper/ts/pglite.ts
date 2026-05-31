import { PGlite } from "@electric-sql/pglite";
// vector
import { vector } from "@electric-sql/pglite/vector";
import { PGLiteSocketServer } from "@electric-sql/pglite-socket";
import { exec } from "child_process";

// Create a PGlite instance
const db = await PGlite.create({
	extensions: { vector },
});

// Create and start a socket server
const server = new PGLiteSocketServer({
	db,
	port: 5433,
	host: "127.0.0.1",
});

await server.start();
console.log("PGlite server started on port 5433");

// after start, run migrations via python3 ../migrator.py
await new Promise<void>((resolve, reject) => {
	exec("DRY=true python3 ../migrator.py", (error, stdout, stderr) => {
		if (error) {
			console.error(`Error running migrations: ${error.message}`);
			reject(error);
			return;
		}
		if (stderr) {
			console.error(`stderr: ${stderr}`);
		}
		console.log(`stdout: ${stdout}`);
		resolve();
	});
});

// Handle graceful shutdown
process.on("SIGINT", async () => {
	await server.stop();
	await db.close();
	console.log("Server stopped and database closed");
	process.exit(0);
});
