import { Mail, Lock, Eye } from "lucide-react";

import fondo from "../../assets/images/CCAA.png";
import logo from "../../assets/logos/logo-campos-australes-normal.png";

function Login() {
  return (
    <div className="min-h-screen flex bg-slate-100">

      {/* Imagen */}

      <div className="hidden lg:flex w-3/5 relative">

        {/* Cuando tengas la imagen */}

        {

        <img
          src={fondo}
          className="absolute inset-0 h-full w-full object-cover"
        />

        }

        <div className="absolute inset-0 bg-gradient-to-br"></div>

        <div className="relative z-10 flex flex-col justify-end p-16 text-white">

          <h1 className="text-5xl font-bold mb-4">

            Sistema de Producción

          </h1>

          <h2 className="text-3xl text-green-200 mb-6">

            Campos Australes

          </h2>

          <p className="max-w-xl text-lg leading-8 text-green-50">

            Plataforma para la gestión integral de la producción,
            trazabilidad, calidad e inventario.

          </p>

        </div>

      </div>

      {/* Login */}

      <div className="flex flex-1 items-center justify-center bg-white">

        <div className="w-full max-w-md px-10">

          {/* Logo */}

          {

          <img
             src={logo}
             className="w-48 mb-10"
          />

          }

          <h2 className="text-4xl font-bold text-slate-800">

            Bienvenido

          </h2>

          <p className="mt-2 mb-10 text-slate-500">

            Inicia sesión para acceder al sistema.

          </p>

          <form className="space-y-6">

            <div>

              <label className="mb-2 block text-sm font-medium text-slate-700">

                Correo electrónico

              </label>

              <div className="flex items-center rounded-xl border border-slate-300 bg-white px-4">

                <Mail className="h-5 w-5 text-slate-400" />

                <input
                  type="email"
                  placeholder="usuario@camposaustrales.cl"
                  className="w-full bg-transparent px-3 py-4 outline-none"
                />

              </div>

            </div>

            <div>

              <label className="mb-2 block text-sm font-medium text-slate-700">

                Contraseña

              </label>

              <div className="flex items-center rounded-xl border border-slate-300 bg-white px-4">

                <Lock className="h-5 w-5 text-slate-400" />

                <input
                  type="password"
                  placeholder="••••••••••••"
                  className="w-full bg-transparent px-3 py-4 outline-none"
                />

                <Eye className="h-5 w-5 cursor-pointer text-slate-400" />

              </div>

            </div>

            <div className="flex items-center justify-between">

              <label className="flex items-center gap-2 text-sm">

                <input type="checkbox" />

                Recordarme

              </label>

              <button
                type="button"
                className="text-sm text-green-700 hover:underline"
              >

                ¿Olvidaste tu contraseña?

              </button>

            </div>

            <button
              className="
              w-full
              rounded-xl
              bg-green-700
              py-4
              font-semibold
              text-white
              transition-all
              duration-300
              hover:bg-green-800
              hover:shadow-xl
              "
            >

              Iniciar sesión

            </button>

          </form>

          <div className="mt-12 text-center text-sm text-slate-400">

            Factory System

            <br />

            Versión 1.0

          </div>

        </div>

      </div>

    </div>
  );
}

export default Login;