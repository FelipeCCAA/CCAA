import { Outlet } from "react-router-dom";

import Navbar from "../components/Navbar/Navbar";


/*
  Estructura de las pantallas internas del sistema: menú lateral fijo a la
  izquierda y el contenido a la derecha.

  <Outlet /> es el hueco donde react-router inserta la página de la ruta
  actual (Dashboard, Producción, etc.). Ver app/routes.tsx.
*/

function MainLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-[#f6f8f7] md:flex-row">

      <Navbar />

      <main className="min-w-0 flex-1">

        <Outlet />

      </main>

    </div>
  );
}


export default MainLayout;
