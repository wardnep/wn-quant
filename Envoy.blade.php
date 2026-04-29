@servers(['prod' => ['wardnep@wn']])

@task('deploy', ['on' => 'prod'])
	whoami
	cd /var/www/wn-quant
	{{-- release=$(date +%Y%m%d%H%M%S)
	git clone git@github.com:wardnep/wn.git $release
	cd $release
	composer install --quiet
	ln -s ../env .env
	rm -rf storage
	ln -s ../storage storage
	ln -s ../../adminer public/adminer
	php artisan migrate --no-interaction
	php artisan optimize
	php artisan config:clear
  	cd ..
	ln -sfn $release current
	find . -maxdepth 1 -name "2*" | sort | head -n -2 | xargs rm -Rf --}}
@endtask
