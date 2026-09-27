from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .forms import NoticiaForm
from .models import Noticia
from .services import noticias_visibles, notificar_noticia

MENSAJE_SOLO_ADMIN = 'Solo un administrador puede publicar o editar noticias.'


@login_required
def lista(request):
    noticias = noticias_visibles(request.user)
    return render(request, 'noticias/lista.html', {'noticias': noticias})


@login_required
def detalle(request, pk):
    # El filtro de visibilidad va dentro del get_object_or_404: una noticia
    # dirigida a otro curso simplemente no existe para este usuario.
    noticia = get_object_or_404(noticias_visibles(request.user), pk=pk)
    return render(request, 'noticias/detalle.html', {'noticia': noticia})


@login_required
def crear(request):
    if not request.user.es_admin():
        return HttpResponseForbidden(MENSAJE_SOLO_ADMIN)

    if request.method == 'POST':
        form = NoticiaForm(request.POST, request.FILES)
        if form.is_valid():
            noticia = form.save(commit=False)
            noticia.publicado_por = request.user
            if request.FILES.get('archivo'):
                noticia.archivo_nombre = request.FILES['archivo'].name
            noticia.save()
            messages.success(request, 'Noticia publicada.')
            avisados = notificar_noticia(noticia, excluir=request.user)
            if avisados:
                messages.info(request, f'Se notificó a {avisados} persona(s).')
            return redirect('noticias:detalle', pk=noticia.pk)
    else:
        form = NoticiaForm()

    return render(request, 'noticias/form.html', {'form': form, 'es_edicion': False})


@login_required
def editar(request, pk):
    if not request.user.es_admin():
        return HttpResponseForbidden(MENSAJE_SOLO_ADMIN)

    noticia = get_object_or_404(Noticia, pk=pk)
    publicada_antes = noticia.publicada

    if request.method == 'POST':
        form = NoticiaForm(request.POST, request.FILES, instance=noticia)
        if form.is_valid():
            noticia = form.save(commit=False)
            if request.FILES.get('archivo'):
                noticia.archivo_nombre = request.FILES['archivo'].name
            elif not noticia.archivo:
                noticia.archivo_nombre = ''
            noticia.save()
            messages.success(request, 'Noticia actualizada.')
            # Solo se avisa en la transición de borrador a publicada: editar una
            # noticia ya publicada no debe volver a notificar a todo el colegio.
            if not publicada_antes and noticia.publicada:
                avisados = notificar_noticia(noticia, excluir=request.user)
                if avisados:
                    messages.info(request, f'Se notificó a {avisados} persona(s).')
            return redirect('noticias:detalle', pk=noticia.pk)
    else:
        form = NoticiaForm(instance=noticia)

    return render(request, 'noticias/form.html', {'form': form, 'noticia': noticia, 'es_edicion': True})


@login_required
def eliminar(request, pk):
    if not request.user.es_admin():
        return HttpResponseForbidden(MENSAJE_SOLO_ADMIN)

    noticia = get_object_or_404(Noticia, pk=pk)
    if request.method == 'POST':
        noticia.delete()
        messages.warning(request, 'Noticia eliminada.')
        return redirect('noticias:lista')
    return render(request, 'noticias/confirmar_eliminar.html', {'noticia': noticia})


def _servir(archivo, nombre, adjunto=True):
    if not archivo:
        raise Http404('El archivo no existe.')
    return FileResponse(
        archivo.open('rb'), as_attachment=adjunto,
        filename=nombre or Path(archivo.name).name,
    )


@login_required
def imagen(request, pk):
    noticia = get_object_or_404(noticias_visibles(request.user), pk=pk)
    return _servir(noticia.imagen, Path(noticia.imagen.name).name if noticia.imagen else '', adjunto=False)


@login_required
def adjunto(request, pk):
    noticia = get_object_or_404(noticias_visibles(request.user), pk=pk)
    return _servir(noticia.archivo, noticia.archivo_nombre)
